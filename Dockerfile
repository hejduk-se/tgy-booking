FROM tiangolo/uwsgi-nginx-flask:python3.7

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . /app
WORKDIR /app