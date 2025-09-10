#!/bin/bash
set -e

echo "Starting AWS Batch Job"
echo "Job Type: ${JOB_TYPE}"
echo "Job ID: ${AWS_BATCH_JOB_ID}"
echo "Job Queue: ${AWS_BATCH_JQ_NAME}"
echo "Job Parameters: ${JOB_PARAMS}"

if [ -z "$JOB_TYPE" ]; then
    echo "ERROR: JOB_TYPE environment variable is not set"
    exit 1
fi

case "$JOB_TYPE" in
    "extractMetricComputation")
        echo "Running Metric Computation job..."
        python /app/jobs/extractMetricComputation.py
        ;;
    "extractMetadata")
        echo "Running Metadata extraction job..."
        python /app/jobs/extractMetadata.py
        ;;
    *)
        echo "ERROR: Unknown JOB_TYPE: $JOB_TYPE"
        echo "Valid options are: extractMetricComputation, extractMetadata"
        exit 1
        ;;
esac

exit_code=$?
echo "Job completed with exit code: $exit_code"
exit $exit_code