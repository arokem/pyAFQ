###############################################################################
# Dockerfile to build pyAFQ
###############################################################################

# Use python base image
FROM python:3.11

ARG COMMIT

# Install pyAFQ
RUN pip install --no-cache-dir git+https://github.com/tractometry/pyAFQ.git@${COMMIT}
RUN pip install fslpy
RUN pyAFQ download

ENTRYPOINT ["pyAFQ"]
