FROM jupyter/scipy-notebook

COPY --chown=${NB_UID}:${NB_GID} mach_perftest_notebook_dev/requirements.txt /tmp/
RUN pip install --quiet --no-cache-dir -r /tmp/requirements.txt && \
    fix-permissions "${CONDA_DIR}" && \
    fix-permissions "/home/${NB_USER}"

ARG CONTAINER_TAG
ENV CONTAINER_TAG=${CONTAINER_TAG:-0.0}

COPY --chown=${NB_UID}:${NB_GID} ./ /app/
WORKDIR /app/

RUN ln -s mach_perftest_notebook_dev/perftestnotebook perftestnotebook

ENTRYPOINT [ "python3", "run_variance_analysis.py" ]
CMD [ "--help" ]
