import React from 'react';
import AnsiLog from '../../components/AnsiLog';

const EnablersStep = ({
    stepName,
    enablersHtml,
    enablersUrl,
    enablerTerms,
    planWithEnablers,
    hlPlanLog,
}) => {
    const rows = React.useMemo(() => {
        if (!Array.isArray(planWithEnablers)) return [];
        return planWithEnablers
            .map((row, index) => {
                const stepIdRaw = row?.step_id;
                const stepId = Number.isFinite(stepIdRaw) ? Number(stepIdRaw) : Number.parseInt(stepIdRaw, 10);
                const step = String(row?.step || '').trim();
                const incoming = Array.isArray(row?.incoming_enablers)
                    ? row.incoming_enablers
                        .map((item) => (Number.isFinite(item) ? Number(item) : Number.parseInt(item, 10)))
                        .filter((item) => Number.isInteger(item))
                    : [];
                return {
                    key: `${index}-${stepId}-${step}`,
                    stepId,
                    step,
                    incoming,
                };
            })
            .filter((row) => Number.isInteger(row.stepId) && row.step.length > 0)
            .sort((a, b) => a.stepId - b.stepId);
    }, [planWithEnablers]);

    return (
        <div>
            <h4 className="placeholder-step-title mb-3">{stepName}</h4>
            {!enablersHtml ? (
                <div className="alert alert-info mb-0" role="alert">
                    No enablers visualization available yet. Run HL total-order planning first.
                </div>
            ) : (
                <div>
                    {rows.length > 0 ? (
                        <div className="card mb-3">
                            <div className="card-header">Plan Actions and Relative Enablers</div>
                            <div className="card-body p-0">
                                <div className="table-responsive">
                                    <table className="table table-sm mb-0">
                                        <thead>
                                            <tr>
                                                <th className="ps-3">Action</th>
                                                <th className="pe-3">Enablers (step IDs)</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {rows.map((row) => (
                                                <tr key={row.key}>
                                                    <td className="ps-3">
                                                        <code>{row.stepId}-{row.step}</code>
                                                    </td>
                                                    <td className="pe-3">
                                                        <code>[{row.incoming.join(', ')}]</code>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    ) : (
                        Array.isArray(enablerTerms) && enablerTerms.length > 0 && (
                            <div className="card mb-3">
                                <div className="card-header">Extracted Enablers</div>
                                <div className="card-body">
                                    <ol className="mb-0">
                                        {enablerTerms.map((term, index) => (
                                            <li key={`${term}-${index}`}>
                                                <code>{term}</code>
                                            </li>
                                        ))}
                                    </ol>
                                </div>
                            </div>
                        )
                    )}

                    {enablersUrl && (
                        <div className="mb-3">
                            <a
                                className="btn btn-outline-primary"
                                href={enablersUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                Open Enablers HTML in a new window
                            </a>
                        </div>
                    )}

                    <div className="hl-plan-visualization-frame-wrap">
                        <iframe
                            title="Enablers Visualization"
                            className="hl-plan-visualization-frame"
                            srcDoc={enablersHtml}
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
};

export default EnablersStep;
