# OpenProject Sidecar
This sidecar configures OpenProject on Kubernetes. It can set `settings` and `auth_sources`. It is used in the [OpenProject Helm Chart](https://github.com/simwak/charts).

It needs the following environment variables:
- DATABASE_USER
- DATABASE_PASSWORD
- DATABASE_HOST
- DATABASE_PORT
- DATABASE_DB
- OPENPROJECT_DEACTIVATE_ADMIN
- OPENPROJECT_DEPLOYMENT

With `OPENPROJECT_DEACTIVATE_ADMIN` = `True` or `true` you can deactivate the default admin user.  
`OPENPROJECT_DEPLOYMENT` need to be the deployment name of the OpenProject deployment.

## Update the image
``` bash
VERSION=X.X.X
docker build -t simwak/openproject-sidecar:$VERSION .
docker push simwak/openproject-sidecar:$VERSION
```