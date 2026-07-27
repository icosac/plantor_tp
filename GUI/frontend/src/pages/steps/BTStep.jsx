import React from 'react';
import AnsiLog from '../../components/AnsiLog';

const statusClass = (status) => {
    if (!status) return '';
    if (status.type === 'success') return 'text-success';
    if (status.type === 'warning') return 'text-warning';
    return 'text-danger';
};

const BTStep = ({
    stepName,
    isGeneratingBt,
    btStatus,
    btHtml,
    btUrl,
    btXml,
    btXmlUrl,
    btLog,
    onRunBtGeneration,
}) => (
    <div>
        <h4 className="placeholder-step-title mb-3">{stepName}</h4>
        <p className="text-muted mb-3">
            Extract the behavior tree from the optimized STN and inspect the generated BT graph.
        </p>

        <div className="d-flex flex-wrap align-items-center gap-2">
            <button
                type="button"
                className="btn btn-primary"
                onClick={onRunBtGeneration}
                disabled={isGeneratingBt}
            >
                {isGeneratingBt ? 'Extracting...' : 'Extract Behavior Tree'}
            </button>
            {btXml && btXmlUrl && (
                <a
                    className="btn btn-outline-primary"
                    href={btXmlUrl}
                    download="bt.xml"
                >
                    Download XML
                </a>
            )}
            {btStatus && (
                <span className={`fw-semibold ${statusClass(btStatus)}`}>
                    {btStatus.message}
                </span>
            )}
        </div>

        {btHtml && (
            <div className="mt-3">
                {btUrl && (
                    <div className="mb-3">
                        <a
                            className="btn btn-outline-secondary"
                            href={btUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                        >
                            Open BT visualization
                        </a>
                    </div>
                )}

                <div className="hl-plan-visualization-frame-wrap">
                    <iframe
                        title="Behavior Tree Visualization"
                        className="hl-plan-visualization-frame"
                        srcDoc={btHtml}
                    />
                </div>

                {btLog && (
                    <details className="mt-3">
                        <summary>BT extraction log</summary>
                        <AnsiLog className="hl-plan-log mt-2 mb-0" text={btLog} />
                    </details>
                )}
            </div>
        )}
    </div>
);

export default BTStep;
