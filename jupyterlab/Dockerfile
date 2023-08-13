FROM jupyter/datascience-notebook:latest

RUN mamba install --yes \
    kafka-python \
    psycopg2-binary \
    geopandas && \
    mamba clean --all -f -y && \
    pip install clickhouse-driver==0.2.6 && \
    fix-permissions "${CONDA_DIR}" && \
    fix-permissions "/home/${NB_USER}"

USER 0

RUN echo $'#!/bin/bash \n cp -R -n /notebooks/* /home/jovyan/ \n fix-permissions "/home/${NB_USER}"' > /usr/local/bin/init.sh \
     && chmod +x /usr/local/bin/init.sh

COPY ./notebooks/ /notebooks

USER ${NB_UID}