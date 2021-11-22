pipeline{

	agent any

	environment {
		REGISTRY="hdavid0510/mjpeg-relay"
		REGISTRY_CREDENTIALS='dockerhub-credential'
		//TAG=":$BUILD_NUMBER"
		TAG="latest"
		DOCKERIMAGE=''
	}

	stages {

		stage('Build') {
			steps {
				script {
					DOCKERIMAGE = docker.build REGISTRY + ":" + TAG
				}
			}
		}

		stage('Push') {
			steps {
				script {
					docker.withRegistry( '', REGISTRY_CREDENTIALS ){
						DOCKERIMAGE.push()
					}
				}
			}
		}
	}

	post {
		always {
			sh "docker rmi $REGISTRY:$TAG"
		}
	}

}
