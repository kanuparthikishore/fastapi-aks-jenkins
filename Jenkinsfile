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
        cpu: 200m
        memory: 256Mi
  - name: docker
    image: docker:24-dind
    securityContext:
      privileged: true
    env:
    - name: DOCKER_TLS_CERTDIR
      value: ""
    resources:
      requests:
        cpu: 300m
        memory: 512Mi
  - name: helm
    image: alpine/helm:3.15.0
    command: [sleep, infinity]
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
  - name: kubectl
    image: bitnami/kubectl:1.29
    command: [sleep, infinity]
    securityContext:
      runAsUser: 0
"""
    }
  }

  environment {
    GHCR_REGISTRY  = "ghcr.io"
    GITHUB_USER    = "kanuparthikishore"
    IMAGE_NAME     = "fastapi-app"
    IMAGE_TAG      = "${env.GIT_COMMIT[0..7]}"
    FULL_IMAGE     = "${GHCR_REGISTRY}/${GITHUB_USER}/${IMAGE_NAME}:${IMAGE_TAG}"
    STAGING_NS     = "fastapi-staging"
    PROD_NS        = "fastapi-prod"
    HELM_CHART     = "./helm-charts/fastapi-app"
  }

  stages {

    stage('Checkout') {
      steps {
        checkout scm
        echo "Building commit: ${env.GIT_COMMIT[0..7]} on branch: ${env.GIT_BRANCH}"
      }
    }

    stage('Test') {
      steps {
        container('python') {
          sh '''
            pip install -r requirements-dev.txt -q
            echo "--- Lint ---"
            flake8 app/ --max-line-length=100 --exclude=__pycache__
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
          junit 'test-results.xml'
        }
      }
    }

    stage('Security scan') {
      steps {
        container('python') {
          sh '''
            pip install bandit pip-audit -q
            echo "--- SAST: Bandit ---"
            bandit -r app/ -f json -o bandit-report.json || true
            bandit -r app/ --severity-level medium || true
            echo "--- Dependency audit ---"
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
              echo "--- Docker login to GHCR ---"
              echo $GITHUB_TOKEN | docker login ghcr.io \
                -u $GITHUB_USER --password-stdin

              echo "--- Build image ---"
              docker build -t $FULL_IMAGE .

              echo "--- Tag as latest ---"
              docker tag $FULL_IMAGE \
                ${GHCR_REGISTRY}/${GITHUB_USER}/${IMAGE_NAME}:latest

              echo "--- Push SHA tag ---"
              docker push $FULL_IMAGE

              echo "--- Push latest tag ---"
              docker push ${GHCR_REGISTRY}/${GITHUB_USER}/${IMAGE_NAME}:latest

              echo "Image pushed: $FULL_IMAGE"
            '''
          }
        }
      }
    }

    stage('Deploy to staging') {
      steps {
        container('helm') {
          sh '''
            echo "--- Deploy to staging namespace ---"
            helm upgrade --install fastapi-staging $HELM_CHART \
              --namespace $STAGING_NS \
              --values $HELM_CHART/values-staging.yaml \
              --set image.tag=$IMAGE_TAG \
              --set image.repository=${GHCR_REGISTRY}/${GITHUB_USER}/${IMAGE_NAME} \
              --wait \
              --timeout 5m \
              --atomic
            echo "Staging deploy complete"
          '''
        }
      }
    }

    stage('Smoke test staging') {
      steps {
        container('kubectl') {
          sh '''
            echo "--- Waiting for pods to be ready ---"
            kubectl rollout status deployment/fastapi-staging \
              -n $STAGING_NS --timeout=120s

            echo "--- Getting staging service IP ---"
            sleep 15
            CLUSTER_IP=$(kubectl get svc fastapi-staging-svc \
              -n $STAGING_NS \
              -o jsonpath='{.spec.clusterIP}')

            echo "Staging ClusterIP: $CLUSTER_IP"

            echo "--- Running smoke tests via port-forward ---"
            kubectl port-forward svc/fastapi-staging-svc \
              18000:8000 -n $STAGING_NS &
            PF_PID=$!
            sleep 5

            curl -f http://localhost:18000/health
            echo "Health check PASSED"

            curl -f http://localhost:18000/api/items
            echo "Items endpoint PASSED"

            kill $PF_PID || true
            echo "Smoke tests PASSED"
          '''
        }
      }
    }

    stage('Approval gate') {
      steps {
        timeout(time: 4, unit: 'HOURS') {
          input message: 'Deploy to production?',
                ok: 'Approve and Deploy',
                submitterParameter: 'APPROVER'
        }
        echo "Approved by: ${env.APPROVER}"
      }
    }

    stage('Deploy to production') {
      steps {
        container('helm') {
          sh '''
            echo "--- Deploy to production namespace ---"
            helm upgrade --install fastapi-prod $HELM_CHART \
              --namespace $PROD_NS \
              --values $HELM_CHART/values-prod.yaml \
              --set image.tag=$IMAGE_TAG \
              --set image.repository=${GHCR_REGISTRY}/${GITHUB_USER}/${IMAGE_NAME} \
              --wait \
              --timeout 5m \
              --atomic
            echo "Production deploy complete"
          '''
        }
      }
    }

    stage('Verify production') {
      steps {
        container('kubectl') {
          sh '''
            kubectl rollout status deployment/fastapi-prod \
              -n $PROD_NS --timeout=120s

            kubectl get pods -n $PROD_NS
            kubectl get svc  -n $PROD_NS
            kubectl get hpa  -n $PROD_NS
            kubectl get ingress -n $PROD_NS

            echo "Production verification PASSED"
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
      echo "Pipeline FAILED — triggering Helm rollback"
      container('helm') {
        sh '''
          helm rollback fastapi-prod 0 \
            --namespace $PROD_NS || true
          echo "Rollback attempted"
        '''
      }
    }
    always {
      echo "Pipeline finished — branch: ${env.GIT_BRANCH}, commit: ${env.GIT_COMMIT[0..7]}"
    }
  }
}
