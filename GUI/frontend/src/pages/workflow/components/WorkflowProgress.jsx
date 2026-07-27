import React from 'react';

const WorkflowProgress = ({
    steps,
    currentStep,
    progress,
    canAccessStep,
    onStepSelect,
}) => (
    <section className="workflow-progress card shadow-sm mb-4">
        <div className="card-body">
            <div className="workflow-progress-header">
                <h5 className="mb-0">Workflow</h5>
                <span className="workflow-step-indicator">
                    Step {currentStep + 1} / {steps.length}
                </span>
            </div>

            <div className="progress mt-3" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round(progress)}>
                <div
                    className="progress-bar"
                    style={{ width: `${progress}%` }}
                ></div>
            </div>

            <div className="workflow-step-list mt-3">
                {steps.map((step, index) => (
                    <button
                        key={step}
                        type="button"
                        className={`workflow-step-chip ${index === currentStep ? 'active' : ''} ${index < currentStep ? 'done' : ''}`}
                        disabled={!canAccessStep(index)}
                        onClick={() => onStepSelect(index)}
                    >
                        <span className="workflow-step-number">{index + 1}</span>
                        <span>{step}</span>
                    </button>
                ))}
            </div>
        </div>
    </section>
);

export default WorkflowProgress;
