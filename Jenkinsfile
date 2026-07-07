pipeline {
  agent {
    kubernetes {
      yaml """
apiVersion: v1
kind: Pod
metadata:
  labels:
    app: jenkins-agent
spec:
  serviceAccountName: jenkins-deployer
  containers:
  - name: python
    image: python:3.12-slim
    command: [sleep, infinity]
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
      limits:
        cpu: 300m
        memory: 256Mi
  - name: docker
    image: docker:24.0-dind
    securityContext:
      privileged: true
    env:
    - name: DOCKER_TLS_CERTDIR
      value: ""
    resources:
      requests:
        cpu: 200m
        memory: 256Mi
      limits:
        cpu: 500m
        memory: 512Mi
  - name: tools
    image: alpine/k8s:1.29.9
    command: [sleep, infinity]
    securityContext:
      runAsUser: 0
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
      limits:
        cpu: 400m
        memory: 256Mi
"""
    }
  }

  environment {
    GHCR_REGISTRY = "ghcr.io"
    GITHUB_USER   = "kanuparthikishore"
    IMAGE_NAME    = "fastapi-app"
    STAGING_NS    = "fastapi-staging"
    PROD_NS       = "fastapi-prod"
    HELM_CHART    = "./helm-charts/fastapi-app"
  }

  stages {

    stage('Checkout') {
      steps {
        checkout scm
        script {
          env.IMAGE_TAG = sh(
            script: "git rev-parse --short HEAD",
            returnStdout: true
          ).trim()
          env.FULL_IMAGE = "${env.GHCR_REGISTRY}/${env.GITHUB_USER}/${env.IMAGE_NAME}:${env.IMAGE_TAG}"
        }
        echo "Building: ${env.FULL_IMAGE}"
      }
    }

    stage('Test') {
      steps {
        container('python') {
          sh '''
            pip install -r requirements-dev.txt -q
            echo "--- Lint ---"
            flake8 app/ --max-line-length=100 --exclude=__pycache__,app/tests
            echo "--- Tests ---"
            pytest app/tests/ \
              --cov=app \
              --cov-report=xml:coverage.xml \
              --cov-report=term-missing \
              --junitxml=test-results.xml \
              -v
          '''
        }
      }
      post {
        always {
          junit allowEmptyResults: true, testResults: 'test-results.xml'
        }
      }
    }

    stage('Security scan') {
      steps {
        container('python') {
          sh '''
            pip install bandit pip-audit -q
            echo "--- Bandit SAST ---"
            bandit -r app/ --severity-level medium || true
            echo "--- pip-audit ---"
            pip-audit -r requirements.txt || true
          '''
        }
      }
    }

    stage('Build and push to GHCR') {
      steps {
        container('docker') {
          withCredentials([string(credentialsId: 'github-token', variable: 'GITHUB_TOKEN')]) {
            sh '''
              echo $GITHUB_TOKEN | docker login ghcr.io \
                -u $GITHUB_USER --password-stdin

              docker build -t $FULL_IMAGE .
              docker tag $FULL_IMAGE \
                ${GHCR_REGISTRY}/${GITHUB_USER}/${IMAGE_NAME}:latest

              docker push $FULL_IMAGE
              docker push ${GHCR_REGISTRY}/${GITHUB_USER}/${IMAGE_NAME}:latest
              echo "Pushed: $FULL_IMAGE"
            '''
          }
        }
      }
    }

    stage('Deploy to staging') {
      steps {
        container('tools') {
          sh '''
            echo "--- Verify tools ---"
            helm version --short
            kubectl version --client

            echo "--- Deploy staging ---"
            helm upgrade --install fastapi-staging $HELM_CHART \
              --namespace $STAGING_NS \
              --values $HELM_CHART/values-staging.yaml \
              --set image.tag=$IMAGE_TAG \
              --set image.repository=${GHCR_REGISTRY}/${GITHUB_USER}/${IMAGE_NAME} \
              --wait \
              --timeout 5m \
              --atomic
          '''
        }
      }
    }

    stage('Smoke test staging') {
      steps {
        container('tools') {
          sh '''
            kubectl rollout status deployment/fastapi-staging \
              -n $STAGING_NS --timeout=120s

            kubectl port-forward svc/fastapi-staging-svc \
              18000:8000 -n $STAGING_NS &
            PF_PID=$!
            sleep 10

            curl -f http://localhost:18000/health
            echo "Health: PASSED"

            curl -f http://localhost:18000/api/items
            echo "Items: PASSED"

            kill $PF_PID || true
          '''
        }
      }
    }

    stage('Approval gate') {
      steps {
        timeout(time: 4, unit: 'HOURS') {
          input message: 'Deploy to production?', ok: 'Approve and Deploy'
        }
      }
    }

    stage('Deploy to production') {
      steps {
        container('tools') {
          sh '''
            helm upgrade --install fastapi-prod $HELM_CHART \
              --namespace $PROD_NS \
              --values $HELM_CHART/values-prod.yaml \
              --set image.tag=$IMAGE_TAG \
              --set image.repository=${GHCR_REGISTRY}/${GITHUB_USER}/${IMAGE_NAME} \
              --wait \
              --timeout 5m \
              --atomic
          '''
        }
      }
    }

    stage('Verify production') {
      steps {
        container('tools') {
          sh '''
            kubectl rollout status deployment/fastapi-prod \
              -n $PROD_NS --timeout=120s
            kubectl get pods    -n $PROD_NS
            kubectl get svc     -n $PROD_NS
            kubectl get hpa     -n $PROD_NS
            kubectl get ingress -n $PROD_NS
            echo "Production VERIFIED"
          '''
        }
      }
    }

  }

  post {
    success {
      echo "Pipeline SUCCESS — image: ${env.FULL_IMAGE}"
    }
    failure {
      echo "Pipeline FAILED"
      container('tools') {
        sh 'helm rollback fastapi-prod -n $PROD_NS || true'
      }
    }
    always {
      echo "Pipeline finished — branch: ${env.GIT_BRANCH}"
    }
  }
}