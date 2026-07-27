import React from 'react';
import AnsiLog from '../../components/AnsiLog';

const statusClass = (status) => {
    if (!status) return '';
    if (status.type === 'success') return 'text-success';
    if (status.type === 'warning') return 'text-warning';
    return 'text-danger';
};

const OptimizedSTNStep = ({
    stepName,
    isGeneratingOptimizedStn,
    optimizedStnStatus,
    optimizedStnHtml,
    optimizedStnUrl,
    optimizedStnExecutionGraphHtml,
    optimizedStnExecutionGraphUrl,
    optimizedStnLog,
    onRunOptimizedStnGeneration,
}) => (
    <div>
        <h4 className="placeholder-step-title mb-3">{stepName}</h4>
        <p className="text-muted mb-3">
            Generate the optimized Simple Temporal Network and inspect the scheduled timeline.
        </p>

        <div className="d-flex flex-wrap align-items-center gap-2">
            <button
                type="button"
                className="btn btn-primary"
                onClick={onRunOptimizedStnGeneration}
                disabled={isGeneratingOptimizedStn}
            >
                {isGeneratingOptimizedStn ? 'Optimizing...' : 'Generate Optimized STN'}
            </button>
            {optimizedStnStatus && (
                <span className={`fw-semibold ${statusClass(optimizedStnStatus)}`}>
                    {optimizedStnStatus.message}
                </span>
            )}
        </div>

        {optimizedStnHtml && (
            <div className="mt-3">
                <div className="d-flex flex-wrap gap-2 mb-3">
                    {optimizedStnUrl && (
                        <a
                            className="btn btn-outline-primary"
                            href={optimizedStnUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                        >
                            Open optimized STN
                        </a>
                    )}
                    {optimizedStnExecutionGraphHtml && optimizedStnExecutionGraphUrl && (
                        <a
                            className="btn btn-outline-secondary"
                            href={optimizedStnExecutionGraphUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                        >
                            Open execution graph
                        </a>
                    )}
                </div>

                <div className="hl-plan-visualization-frame-wrap">
                    <iframe
                        title="Optimized STN Visualization"
                        className="hl-plan-visualization-frame"
                        srcDoc={optimizedStnHtml}
                    />
                </div>

                {optimizedStnLog && (
                    <details className="mt-3">
                        <summary>Optimized STN log</summary>
                        <AnsiLog className="hl-plan-log mt-2 mb-0" text={optimizedStnLog} />
                    </details>
                )}
            </div>
        )}
    </div>
);

export default OptimizedSTNStep;
