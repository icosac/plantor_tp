import React from 'react';
import AnsiLog from '../../components/AnsiLog';

const normalizeToPlanSteps = (steps) => {
    if (!Array.isArray(steps)) return [];

    return steps
        .map((step, index) => {
            const raw = String(step || '').trim();
            const match = raw.match(/^(\d+)\s*-\s*(.+)$/);
            if (!match) {
                return { index, order: Number.POSITIVE_INFINITY, display: raw };
            }
            return { index, order: Number.parseInt(match[1], 10), display: match[2].trim() };
        })
        .sort((a, b) => {
            if (a.order === b.order) return a.index - b.index;
            return a.order - b.order;
        })
        .map((item) => item.display);
};

const PlanningStep = ({
    currentStep,
    stepName,
    isGeneratingHlPlan,
    hlPlanStatus,
    hlPlanFound,
    planningMaxDepth,
    onPlanningMaxDepthChange,
    planningTimeoutSeconds,
    onPlanningTimeoutSecondsChange,
    hlPlanHtml,
    hlPlanUrl,
    hlPlanLog,
    toPlanSteps,
    onRunHlPlanGeneration,
    onRunHlSearchDebug,
    onStopHlPlanGeneration,
}) => {
    const normalizedToPlanSteps = React.useMemo(
        () => normalizeToPlanSteps(toPlanSteps),
        [toPlanSteps],
    );

    if (currentStep === 4) {
        return (
            <div>
                <h4 className="placeholder-step-title mb-3">{stepName}</h4>
                <p className="text-muted mb-3">
                    Generate the high-level total-order plan.
                </p>

                <div className="row g-3 mb-3">
                    <div className="col-12 col-md-4">
                        <label className="form-label fw-semibold" htmlFor="planning-max-depth">
                            Max depth
                        </label>
                        <input
                            id="planning-max-depth"
                            type="number"
                            className="form-control"
                            min="-1"
                            step="1"
                            value={planningMaxDepth}
                            onChange={(event) => onPlanningMaxDepthChange(event.target.value)}
                            disabled={isGeneratingHlPlan}
                        />
                    </div>
                    <div className="col-12 col-md-4">
                        <label className="form-label fw-semibold" htmlFor="planning-timeout-seconds">
                            Timeout
                        </label>
                        <div className="input-group">
                            <input
                                id="planning-timeout-seconds"
                                type="number"
                                className="form-control"
                                min="1"
                                step="1"
                                value={planningTimeoutSeconds}
                                onChange={(event) => onPlanningTimeoutSecondsChange(event.target.value)}
                                disabled={isGeneratingHlPlan}
                            />
                            <span className="input-group-text">seconds</span>
                        </div>
                    </div>
                </div>

                <div className="d-flex flex-wrap align-items-center gap-2">
                    <button
                        type="button"
                        className="btn btn-primary"
                        onClick={onRunHlPlanGeneration}
                        disabled={isGeneratingHlPlan}
                    >
                        {isGeneratingHlPlan ? 'Planning...' : 'Run HL Total-Order Planning'}
                    </button>
                    <button
                        type="button"
                        className="btn btn-danger"
                        onClick={onStopHlPlanGeneration}
                        disabled={!isGeneratingHlPlan}
                    >
                        Stop planner
                    </button>
                    {hlPlanStatus && (
                        <span
                            className={`fw-semibold ${
                                hlPlanStatus.type === 'success'
                                    ? 'text-success'
                                    : (hlPlanStatus.type === 'warning' || hlPlanStatus.type === 'no-plan' ? 'text-warning' : 'text-danger')
                            }`}
                        >
                            {hlPlanStatus.message}
                        </span>
                    )}
                </div>

                {hlPlanStatus?.type === 'no-plan' && !hlPlanHtml && (
                    <div className="mt-3 d-flex flex-wrap align-items-center gap-2">
                        <button
                            type="button"
                            className="btn btn-outline-primary"
                            onClick={onRunHlSearchDebug}
                            disabled={isGeneratingHlPlan}
                        >
                            Run search debug
                        </button>
                    </div>
                )}

                {hlPlanStatus?.type === 'error' && hlPlanLog && !hlPlanHtml && (
                    <details className="mt-3" open>
                        <summary>Planner log</summary>
                        <AnsiLog className="hl-plan-log mt-2 mb-0" text={hlPlanLog} />
                    </details>
                )}

                {hlPlanHtml && (
                    <div className="mt-3">
                        {hlPlanUrl && (
                            <div className="mb-3">
                                <a
                                    className="btn btn-outline-primary"
                                    href={hlPlanUrl}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                >
                                    Open HTML in a new window
                                </a>
                            </div>
                        )}

                        <div className="hl-plan-visualization-frame-wrap">
                            <iframe
                                title="High-Level Plan Visualization"
                                className="hl-plan-visualization-frame"
                                srcDoc={hlPlanHtml}
                            />
                        </div>

                        {hlPlanLog && (
                            <details className="mt-3">
                                <summary>Planner log</summary>
                                <AnsiLog className="hl-plan-log mt-2 mb-0" text={hlPlanLog} />
                            </details>
                        )}
                    </div>
                )}
            </div>
        );
    }

    return (
        <div>
            <h4 className="placeholder-step-title mb-3">{stepName}</h4>
            {!hlPlanFound ? (
                <div className="alert alert-info mb-0" role="alert">
                    No generated plan available yet. Go back to Generate Plan and run the planner first.
                </div>
            ) : (
                <>
                    <div className="card mb-3">
                        <div className="card-header">Total-Order Plan</div>
                        <div className="card-body">
                            {normalizedToPlanSteps.length === 0 ? (
                                <div className="text-muted mb-0">
                                    No total-order plan steps were extracted from <code>apply_mappings</code>.
                                </div>
                            ) : (
                                <ol className="mb-0">
                                    {normalizedToPlanSteps.map((step, index) => (
                                        <li key={`${step}-${index}`}>
                                            <code>{step}</code>
                                        </li>
                                    ))}
                                </ol>
                            )}
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};

export default PlanningStep;
