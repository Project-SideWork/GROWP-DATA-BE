pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        timestamps()
    }

    environment {
        IMAGE_NAME = 'growp-analysis'
        IMAGE_TAG = "${env.GIT_COMMIT ?: env.BUILD_NUMBER}"
        TEST_IMAGE = "growp-analysis-test:${env.BUILD_NUMBER}"
        IMAGE_ARCHIVE = 'growp-analysis.tar'
        BASTION_HOST = '133.186.134.138'
        BASTION_USER = 'ubuntu'
        APP_SERVER_ALIAS = 'growp'
        BASTION_TEMP_DIR = '/home/ubuntu/temp'
        APP_DIR = '/home/ubuntu/app'
        API_CONTAINER = 'growp-analysis-api'
        CONSUMER_CONTAINER = 'growp-analysis-consumer'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Test') {
            steps {
                sh '''
                  docker build --target test -t ${TEST_IMAGE} .
                  docker run --rm ${TEST_IMAGE}
                '''
            }
        }

        stage('Build Runtime Image') {
            steps {
                sh 'docker build --target runtime -t ${IMAGE_NAME}:${IMAGE_TAG} .'
            }
        }

        stage('Save Docker Image') {
            steps {
                sh '''
                  docker save ${IMAGE_NAME}:${IMAGE_TAG} -o ${IMAGE_ARCHIVE}
                  chmod 644 ${IMAGE_ARCHIVE}
                  ls -lh ${IMAGE_ARCHIVE}
                '''
            }
        }

        stage('Deploy') {
            steps {
                withCredentials([
                    sshUserPrivateKey(
                        credentialsId: 'nhn-ssh-key',
                        keyFileVariable: 'SSH_KEY'
                    ),
                    string(credentialsId: 'kafka-host', variable: 'KAFKA_HOST'),
                    string(credentialsId: 'kafka-port', variable: 'KAFKA_PORT')
                ]) {
                    sh '''
set -eu

cat > .env.production <<EOF
APP_ENV=prod
LOG_LEVEL=INFO
BACKEND_BASE_URL=http://127.0.0.1:8080
BACKEND_API_KEY=
REQUEST_TIMEOUT_SECONDS=10
DELIVERY_MAX_ATTEMPTS=3
BACKEND_FETCH_CONCURRENCY=5
KAFKA_ENABLED=false
KAFKA_BOOTSTRAP_SERVERS=${KAFKA_HOST}:${KAFKA_PORT}
KAFKA_CLIENT_ID=growp-analysis-pipeline
KAFKA_CONSUMER_GROUP_ID=growp-analysis-consumer
EOF

chmod 600 "${SSH_KEY}" .env.production

scp -i "${SSH_KEY}" -o StrictHostKeyChecking=no \
  "${IMAGE_ARCHIVE}" .env.production \
  "${BASTION_USER}@${BASTION_HOST}:${BASTION_TEMP_DIR}/"

ssh -i "${SSH_KEY}" -o StrictHostKeyChecking=no \
  "${BASTION_USER}@${BASTION_HOST}" <<ENDSSH
set -eu
cd "${BASTION_TEMP_DIR}"

scp -o StrictHostKeyChecking=no \
  "${IMAGE_ARCHIVE}" .env.production \
  "${APP_SERVER_ALIAS}:${APP_DIR}/"

ssh -o StrictHostKeyChecking=no "${APP_SERVER_ALIAS}" <<INNERSSH
set -eu
cd "${APP_DIR}"

docker load -i "${IMAGE_ARCHIVE}"
docker stop "${API_CONTAINER}" "${CONSUMER_CONTAINER}" 2>/dev/null || true
docker rm "${API_CONTAINER}" "${CONSUMER_CONTAINER}" 2>/dev/null || true

mkdir -p logs/analysis-api logs/analysis-consumer
sudo chown -R 10001:10001 logs/analysis-api logs/analysis-consumer

docker run -d \
  --name "${API_CONTAINER}" \
  --network host \
  --env-file .env.production \
  -v "${APP_DIR}/logs/analysis-api:/app/logs" \
  --restart unless-stopped \
  "${IMAGE_NAME}:${IMAGE_TAG}"

docker run -d \
  --name "${CONSUMER_CONTAINER}" \
  --network host \
  --env-file .env.production \
  -v "${APP_DIR}/logs/analysis-consumer:/app/logs" \
  --restart unless-stopped \
  "${IMAGE_NAME}:${IMAGE_TAG}" \
  python -m app.clients.kafka_consumer

sleep 10
docker exec "${API_CONTAINER}" python -c \
  "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=5)"
docker inspect -f '{{.State.Running}}' "${CONSUMER_CONTAINER}" | grep -qx true

rm -f "${IMAGE_ARCHIVE}" .env.production
INNERSSH

rm -f "${BASTION_TEMP_DIR}/${IMAGE_ARCHIVE}" \
  "${BASTION_TEMP_DIR}/.env.production"
ENDSSH
                    '''
                }
            }
        }
    }

    post {
        always {
            sh '''
              rm -f ${IMAGE_ARCHIVE} .env.production || true
              docker image rm ${TEST_IMAGE} 2>/dev/null || true
            '''
        }
    }
}
