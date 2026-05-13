FROM python:3.11-slim

ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV HF_ENDPOINT=https://hf-mirror.com

RUN apt-get update && apt-get install -y wget aria2 curl && rm -rf /var/lib/apt/lists/*

RUN wget -q https://hf-mirror.com/hfd/hfd.sh -O /hfd.sh && chmod +x /hfd.sh

WORKDIR /models
CMD ["/bin/bash"]