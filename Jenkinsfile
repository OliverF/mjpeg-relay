pipeline{

	agent any

	environment {
		IMAGE_NAME="hdavid0510/mjpeg-relay"
		IMAGE_TAG="latest"
		REGISTRY_CREDENTIALS=credentials('dockerhub-credential')
	}

	stages {
		stage('Init') {
			steps {
				echo 'Initializing.'

				sh 'echo $REGISTRY_CREDENTIALS_PSW | docker login -u $REGISTRY_CREDENTIALS_USR --password-stdin'
				echo "Running ${env.BUILD_ID} on ${env.JENKINS_URL}"
				echo "Building ${IMAGE_NAME} on branch ${IMAGE_TAG}"
			}
		}
		stage('Build/Push') {
			steps {
				echo 'Building image and pushing to DockerHub.'

				sh 'docker buildx build --push --platform linux/386,linux/amd64,linux/arm/v5,linux/arm/v7,linux/arm64,linux/mips64le,linux/ppc64le,linux/s390x -t $IMAGE_NAME:$IMAGE_TAG .'
			}
		}
	}

	post {
		always {
			sh 'docker logout'
		}
	}

}
