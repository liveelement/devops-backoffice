# Publishing DevOps backoffice

Public repo: https://github.com/liveelement/devops-backoffice  
Image: `ghcr.io/liveelement/devops-backoffice:0.1.0`

## Local image build / push

```bash
cd products/devops-backoffice
docker build -t ghcr.io/liveelement/devops-backoffice:0.1.0 .
echo $GITHUB_TOKEN | docker login ghcr.io -u liveelement --password-stdin
docker push ghcr.io/liveelement/devops-backoffice:0.1.0
docker tag ghcr.io/liveelement/devops-backoffice:0.1.0 ghcr.io/liveelement/devops-backoffice:latest
docker push ghcr.io/liveelement/devops-backoffice:latest
```

Make the package public in GitHub → Packages → Package settings → Change visibility.

## CI workflow

`.github/workflows/publish-image.yml` lives in the catalog copy. The initial GitHub OAuth push lacked the `workflow` scope, so the workflow is not on `main` yet. When a token with `workflow` scope is available:

```bash
cd products/devops-backoffice
git add .github/workflows/publish-image.yml
git commit -m "Add GHCR publish workflow"
git push
```

## Tag a release

```bash
git tag v0.1.0
git push origin v0.1.0
```
