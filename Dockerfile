ARG        PYTHON_TAG=3
FROM       python:${PYTHON_TAG} AS base

# Add some metadata
LABEL      app.name="InterPlanetary Wayback (IPWB)" \
           app.description="A distributed and persistent archive replay system using IPFS" \
           app.license="MIT License" \
           app.license.url="https://github.com/oduwsdl/ipwb/blob/master/LICENSE" \
           app.repo.url="https://github.com/oduwsdl/ipwb" \
           app.authors="Mat Kelly <@machawk1> and Sawood Alam <@ibnesayeed>"

# Add a custom entrypoint script
COPY       entrypoint.sh /usr/local/bin/
RUN        chmod a+x /usr/local/bin/entrypoint.sh

# Enable unbuffered STDOUT logging
ENV        PYTHONUNBUFFERED=1

# Create folders for WARC, CDXJ and IPFS stores
RUN        mkdir -p /data/{warc,cdxj,ipfs}

# Download and install IPFS
ENV        IPFS_PATH=/data/ipfs
ARG        IPFS_VERSION=v0.32.1
ARG        BUILDARCH
RUN        cd /tmp \
           && wget -q https://dist.ipfs.tech/kubo/${IPFS_VERSION}/kubo_${IPFS_VERSION}_linux-$BUILDARCH.tar.gz \
           && tar xvfz kubo*.tar.gz \
           && mv kubo/ipfs /usr/local/bin/ipfs \
           && rm -rf kubo* \
           && ipfs init

# Make necessary changes to prepare the environment for IPWB
RUN        apt update && apt install -y locales \
           && rm -rf /var/lib/apt/lists/* \
           && echo "en_US.UTF-8 UTF-8" > /etc/locale.gen \
           && locale-gen

# Install basic requirements
WORKDIR    /ipwb
COPY       requirements.txt ./
RUN        pip install -r requirements.txt


# Standard JS lint
FROM       node
WORKDIR    /ipwb
COPY       . ./
ARG        SKIPTEST=false
RUN        $SKIPTEST || npm install -g standard
RUN        $SKIPTEST || standard


# Testing stage
FROM base AS test

# Install necessary test requirements
COPY       test-requirements.txt ./
RUN        pip install -r test-requirements.txt

# Perform tests
COPY       . ./
ARG        SKIPTEST=false
RUN        $SKIPTEST || pycodestyle
RUN        $SKIPTEST || (ipfs daemon & while ! curl -s localhost:5001 > /dev/null; do sleep 1; done && py.test -s --cov=./)


# Final production image
FROM base

# Install IPWB from the source code
COPY       . ./
RUN        python setup.py install

# Run ipfs daemon in background
# Wait for the daemon to be ready
# Runs provided command
ENTRYPOINT ["entrypoint.sh"]

# Index a sample WARC file and replay it
CMD        ["ipwb", "replay"]
