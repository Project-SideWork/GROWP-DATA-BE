pipeline {
    agent any

    options {
        skipDefaultCheckout(true)
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
        APP_SERVER_ALIAS = 'analytics'
        BASTION_TEMP_DIR = '/home/ubuntu/temp'
        APP_DIR = '/opt/growp/app'
        API_CONTAINER = 'growp-analysis-api'
        CONSUMER_CONTAINER = 'growp-analysis-consumer'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm

                script {
                    env.IMAGE_TAG = sh(
                        script: 'git rev-parse HEAD',
                        returnStdout: true
                    ).trim()
                }

                echo "IMAGE_TAG=${env.IMAGE_TAG}"
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
                    )
                ]) {
                    sh '''
set -eu

chmod 600 "${SSH_KEY}"

scp -i "${SSH_KEY}" -o StrictHostKeyChecking=no \
  "${IMAGE_ARCHIVE}" compose.prod.yml \
  "${BASTION_USER}@${BASTION_HOST}:${BASTION_TEMP_DIR}/"

ssh -i "${SSH_KEY}" -o StrictHostKeyChecking=no \
  "${BASTION_USER}@${BASTION_HOST}" <<ENDSSH
set -eu
cd "${BASTION_TEMP_DIR}"

scp -o StrictHostKeyChecking=no \
  "${IMAGE_ARCHIVE}" compose.prod.yml \
  "${APP_SERVER_ALIAS}:${APP_DIR}/"

ssh -o StrictHostKeyChecking=no "${APP_SERVER_ALIAS}" <<INNERSSH
set -eu
cd "${APP_DIR}"

docker load -i "${IMAGE_ARCHIVE}"

set -a
. /opt/growp/config/production.env
set +a


export IMAGE_TAG="${IMAGE_TAG}"

docker stack deploy \
  --resolve-image never \
  -c compose.prod.yml \
  growp

rm -f ${IMAGE_ARCHIVE}
INNERSSH

rm -f \
  "${BASTION_TEMP_DIR}/${IMAGE_ARCHIVE}" \
  "${BASTION_TEMP_DIR}/compose.prod.yml"
ENDSSH

                    '''
                }
            }
        }
    }

    post {
        always {
            sh '''
              rm -f ${IMAGE_ARCHIVE} || true
              docker image rm ${TEST_IMAGE} 2>/dev/null || true
            '''
        }
    }
}
