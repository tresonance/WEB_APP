#!/bin/bash
echo "from django.contrib.auth.models import User; User.objects.create_superuser($DJANGO_SUPERUSER_USERNAME,$DJANGO_SUPERUSER_EMAIL,$DJANGO_SUPERUSER_PASSWORD)" | python /usr/src/app/myproject/manage.py shell 