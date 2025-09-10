const AWS = require('aws-sdk');
const dotenv = require('dotenv');

// Load environment variables from .env file
dotenv.config();

/**
 * AWS Batch Client for Node.js Integration
 * 
 * This module can be integrated into your existing Node.js server
 * to submit jobs to AWS Batch.
 * 
 * Usage:
 * const batchClient = require('./batch-client');
 * await batchClient.submitMetricComputationJob({ source: 'api' });
 */

class BatchClient {
    constructor(config = {}) {
        this.region = config.region || process.env.AWS_REGION || 'eu-central-1';
        this.jobQueueName = config.jobQueueName || process.env.BATCH_JOB_QUEUE || 'appalti-batch-job-queue';
        
        this.batch = new AWS.Batch({ region: this.region });
        
        this.jobDefinitions = {
            metricComputation: config.metricComputationJobDef || 
                              process.env.METRIC_COMPUTATION_JOB_DEF || 
                              'appalti-batch-metric-computation',
            metadataExtraction: config.metadataExtractionJobDef || 
                               process.env.METADATA_EXTRACTION_JOB_DEF || 
                               'appalti-batch-metadata-extraction'
        };
    }

    /**
     * Submit a metric computation job
     * @param {Object} parameters - Job parameters
     * @param {Object} options - Additional options
     * @returns {Promise<Object>} Job submission result
     */
    async submitMetricComputationJob(parameters = {}, options = {}) {
        return this.submitJob('metricComputation', parameters, options);
    }

    /**
     * Submit a metadata extraction job
     * @param {Object} parameters - Job parameters
     * @param {Object} options - Additional options
     * @returns {Promise<Object>} Job submission result
     */
    async submitMetadataExtractionJob(parameters = {}, options = {}) {
        return this.submitJob('metadataExtraction', parameters, options);
    }

    /**
     * Generic job submission method
     * @param {string} jobType - Type of job to submit
     * @param {Object} parameters - Job parameters
     * @param {Object} options - Additional options
     * @returns {Promise<Object>} Job submission result
     */
    async submitJob(jobType, parameters = {}, options = {}) {
        const jobName = options.jobName || `${jobType}-${Date.now()}`;
        const jobDefinition = this.jobDefinitions[jobType];
        
        if (!jobDefinition) {
            throw new Error(`Unknown job type: ${jobType}`);
        }

        // Convert all parameters to strings for AWS Batch
        const stringParameters = {};
        for (const [key, value] of Object.entries(parameters)) {
            stringParameters[key] = typeof value === 'string' ? value : JSON.stringify(value);
        }

        const params = {
            jobName: jobName,
            jobQueue: this.jobQueueName,
            jobDefinition: jobDefinition,
            parameters: stringParameters,
            containerOverrides: {
                environment: [
                    {
                        name: 'JOB_PARAMS',
                        value: JSON.stringify(parameters)
                    }
                ]
            }
        };

        // Add optional overrides
        if (options.vcpus) {
            params.containerOverrides.resourceRequirements = params.containerOverrides.resourceRequirements || [];
            params.containerOverrides.resourceRequirements.push({
                type: 'VCPU',
                value: options.vcpus.toString()
            });
        }

        if (options.memory) {
            params.containerOverrides.resourceRequirements = params.containerOverrides.resourceRequirements || [];
            params.containerOverrides.resourceRequirements.push({
                type: 'MEMORY',
                value: options.memory.toString()
            });
        }

        if (options.timeout) {
            params.timeout = {
                attemptDurationSeconds: options.timeout
            };
        }

        try {
            const result = await this.batch.submitJob(params).promise();
            console.log(`Job submitted successfully: ${result.jobId}`);
            return {
                success: true,
                jobId: result.jobId,
                jobName: result.jobName,
                jobArn: result.jobArn
            };
        } catch (error) {
            console.error('Error submitting job:', error);
            throw error;
        }
    }

    /**
     * Get job status
     * @param {string} jobId - AWS Batch job ID
     * @returns {Promise<Object>} Job status
     */
    async getJobStatus(jobId) {
        try {
            const result = await this.batch.describeJobs({
                jobs: [jobId]
            }).promise();

            if (result.jobs && result.jobs.length > 0) {
                const job = result.jobs[0];
                return {
                    jobId: job.jobId,
                    jobName: job.jobName,
                    status: job.status,
                    statusReason: job.statusReason,
                    createdAt: job.createdAt,
                    startedAt: job.startedAt,
                    stoppedAt: job.stoppedAt,
                    container: job.container
                };
            } else {
                throw new Error(`Job not found: ${jobId}`);
            }
        } catch (error) {
            console.error('Error getting job status:', error);
            throw error;
        }
    }

    /**
     * Cancel a job
     * @param {string} jobId - AWS Batch job ID
     * @param {string} reason - Cancellation reason
     * @returns {Promise<Object>} Cancellation result
     */
    async cancelJob(jobId, reason = 'User requested cancellation') {
        try {
            const result = await this.batch.cancelJob({
                jobId: jobId,
                reason: reason
            }).promise();
            
            console.log(`Job cancelled successfully: ${jobId}`);
            return {
                success: true,
                jobId: jobId
            };
        } catch (error) {
            console.error('Error cancelling job:', error);
            throw error;
        }
    }

    /**
     * List jobs in the queue
     * @param {Object} options - List options
     * @returns {Promise<Array>} List of jobs
     */
    async listJobs(options = {}) {
        const params = {
            jobQueue: this.jobQueueName,
            jobStatus: options.status || 'RUNNING',
            maxResults: options.maxResults || 100
        };

        if (options.nextToken) {
            params.nextToken = options.nextToken;
        }

        try {
            const result = await this.batch.listJobs(params).promise();
            return {
                jobs: result.jobSummaryList.map(job => ({
                    jobId: job.jobId,
                    jobName: job.jobName,
                    status: job.status,
                    statusReason: job.statusReason,
                    createdAt: job.createdAt,
                    startedAt: job.startedAt,
                    stoppedAt: job.stoppedAt
                })),
                nextToken: result.nextToken
            };
        } catch (error) {
            console.error('Error listing jobs:', error);
            throw error;
        }
    }
}

// Example Express.js integration
function setupExpressRoutes(app, batchClient) {
    // Submit metric computation job
    app.post('/api/batch/metric-computation', async (req, res) => {
        try {
            const result = await batchClient.submitMetricComputationJob(req.body);
            res.json(result);
        } catch (error) {
            res.status(500).json({ error: error.message });
        }
    });

    // Submit metadata extraction job
    app.post('/api/batch/metadata-extraction', async (req, res) => {
        try {
            const result = await batchClient.submitMetadataExtractionJob(req.body);
            res.json(result);
        } catch (error) {
            res.status(500).json({ error: error.message });
        }
    });

    // Get job status
    app.get('/api/batch/jobs/:jobId', async (req, res) => {
        try {
            const result = await batchClient.getJobStatus(req.params.jobId);
            res.json(result);
        } catch (error) {
            res.status(500).json({ error: error.message });
        }
    });

    // Cancel job
    app.delete('/api/batch/jobs/:jobId', async (req, res) => {
        try {
            const result = await batchClient.cancelJob(req.params.jobId, req.body.reason);
            res.json(result);
        } catch (error) {
            res.status(500).json({ error: error.message });
        }
    });

    // List jobs
    app.get('/api/batch/jobs', async (req, res) => {
        try {
            const result = await batchClient.listJobs({
                status: req.query.status,
                maxResults: parseInt(req.query.maxResults) || 100,
                nextToken: req.query.nextToken
            });
            res.json(result);
        } catch (error) {
            res.status(500).json({ error: error.message });
        }
    });
}

// Export for use in your Node.js application
module.exports = BatchClient;
module.exports.setupExpressRoutes = setupExpressRoutes;

// Example usage in your existing Node.js server:
/*
const express = require('express');
const BatchClient = require('./batch-client');

const app = express();
app.use(express.json());

const batchClient = new BatchClient({
    region: process.env.AWS_REGION || 'eu-central-1',
    jobQueueName: process.env.BATCH_JOB_QUEUE || 'appalti-batch-job-queue',
    metricComputationJobDef: process.env.METRIC_COMPUTATION_JOB_DEF || 'appalti-batch-metric-computation',
    metadataExtractionJobDef: process.env.METADATA_EXTRACTION_JOB_DEF || 'appalti-batch-metadata-extraction'
});

// Setup routes
BatchClient.setupExpressRoutes(app, batchClient);

// Or use directly
app.post('/custom-endpoint', async (req, res) => {
    const result = await batchClient.submitMetricComputationJob({
        source: 'custom',
        data: req.body
    });
    res.json(result);
});
*/