FROM python:3.11.13-slim-bookworm
WORKDIR /audit
ENV PYTHONUNBUFFERED=1 MPLBACKEND=Agg PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src src
COPY tests tests
COPY data data
COPY docs docs
COPY findings findings
COPY supplementary supplementary
COPY technical_report.md .
COPY README.md Makefile Dockerfile ./
COPY ApertusChoiceAudit_Report.pdf ./
RUN python -m unittest discover -s tests
CMD ["python", "src/run_all.py"]
