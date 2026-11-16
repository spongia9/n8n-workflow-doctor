FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /build
COPY deploy/backend/build.lock deploy/backend/requirements.lock /locks/
RUN python -m pip install --require-hashes -r /locks/build.lock \
    && python -m pip download --only-binary=:all: --require-hashes -r /locks/requirements.lock -d /wheels
COPY pyproject.toml LICENSE ./
COPY src/ ./src/
RUN python -m pip wheel --no-deps --no-build-isolation --wheel-dir /project-wheel .

FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 TMPDIR=/tmp WORKFLOW_DOCTOR_CONTAINER=1
WORKDIR /app
COPY --from=builder /wheels /wheels
COPY --from=builder /project-wheel /project-wheel
COPY deploy/backend/requirements.lock /requirements.lock
RUN python -m pip install --no-index --find-links=/wheels --require-hashes -r /requirements.lock \
    && python -m pip install --no-index --no-deps /project-wheel/*.whl \
    && python -m pip check \
    && rm -rf /wheels /project-wheel \
    && groupadd --gid 10001 doctor \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin doctor
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import json,urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2); assert r.status==200 and json.load(r)['status']=='ok'"]
STOPSIGNAL SIGTERM
CMD ["python", "-m", "workflow_doctor.api.container"]
