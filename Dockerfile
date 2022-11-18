FROM python:3.10-slim-bullseye

WORKDIR /var/www/app

# create .venv dir (this is where pipenv will install)
RUN mkdir .venv

# install dep
RUN pip install --upgrade pip
RUN pip install --upgrade pipenv
RUN apt-get update && apt-get install iproute2 tzdata git -y

COPY . /var/www/app

# set commit version
RUN sed -i "s/development/$(git rev-parse HEAD)/g" /var/www/app/version.py

RUN pipenv install --deploy

EXPOSE 5000

# timezone default
ENV TZ Europe/Stockholm

CMD [ "/var/www/app/entrypoint.sh" ]
