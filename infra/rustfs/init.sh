#!/bin/sh
set -eu

rc alias set local http://risk-rustfs:9000 "$RUSTFS_ROOT_ACCESS_KEY" "$RUSTFS_ROOT_SECRET_KEY" --region us-east-1 --bucket-lookup path
rc bucket create "local/$STORAGE_BUCKET" --ignore-existing

printf '<CORSConfiguration><CORSRule>' > /tmp/cors.xml
origins="$PUBLIC_ORIGINS"
while [ -n "$origins" ]; do
  case "$origins" in
    *,*) origin=${origins%%,*}; origins=${origins#*,} ;;
    *) origin=$origins; origins= ;;
  esac
  case "$origin" in
    http://*|https://*) ;;
    *) echo "Invalid PUBLIC_ORIGINS entry" >&2; exit 1 ;;
  esac
  # Reject characters that could break the XML document.
  case "$origin" in
    *[!A-Za-z0-9.:/_-]*) echo "Invalid PUBLIC_ORIGINS entry" >&2; exit 1 ;;
  esac
  printf '<AllowedOrigin>%s</AllowedOrigin>' "$origin" >> /tmp/cors.xml
done
printf '<AllowedMethod>GET</AllowedMethod><AllowedMethod>PUT</AllowedMethod><AllowedMethod>HEAD</AllowedMethod><AllowedHeader>*</AllowedHeader><ExposeHeader>ETag</ExposeHeader><MaxAgeSeconds>3600</MaxAgeSeconds></CORSRule></CORSConfiguration>\n' >> /tmp/cors.xml
rc bucket cors set "local/$STORAGE_BUCKET" /tmp/cors.xml

# The app identity only sees its document bucket; root is held by this one-shot container.
cat > /tmp/policy.json <<EOF
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["s3:ListBucket"],"Resource":["arn:aws:s3:::$STORAGE_BUCKET"]},{"Effect":"Allow","Action":["s3:GetObject","s3:PutObject","s3:DeleteObject"],"Resource":["arn:aws:s3:::$STORAGE_BUCKET/*"]}]}
EOF
rc admin policy create local risk-documents /tmp/policy.json
rc admin user add local "$STORAGE_ACCESS_KEY" "$STORAGE_SECRET_KEY"
rc admin policy attach local risk-documents --user "$STORAGE_ACCESS_KEY"
