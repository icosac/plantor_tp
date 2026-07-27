import React from 'react';

const PromptStep = ({
    currentStep,
    highLevelDesc,
    lowLevelDesc,
    onHighLevelChange,
    onLowLevelChange,
    llmConfigs,
    selectedLlm,
    onSelectLlm,
    llmLoadError,
    isChecking,
    validationStatus,
    skipConsistencyCheck,
    onSkipChange,
    onRunCheck,
}) => {
    const renderPromptInputs = () => (
        <div className="row">
            <div className="col-md-6">
                <div className="card shadow-sm p-3 mb-3">
                    <div className="card-header bg-light text-center fw-semibold">
                        High-Level Description
                    </div>
                    <div className="card-body">
                        <textarea
                            className="form-control"
                            rows="10"
                            value={highLevelDesc}
                            onChange={(e) => onHighLevelChange(e.target.value)}
                            placeholder="Enter the high-level task description here"
                        ></textarea>
                    </div>
                </div>
            </div>

            <div className="col-md-6">
                <div className="card shadow-sm p-3 mb-3">
                    <div className="card-header bg-light text-center fw-semibold">
                        Low-Level Description
                    </div>
                    <div className="card-body">
                        <textarea
                            className="form-control"
                            rows="10"
                            value={lowLevelDesc}
                            onChange={(e) => onLowLevelChange(e.target.value)}
                            placeholder="Enter the low-level task description here"
                        ></textarea>
                    </div>
                </div>
            </div>
        </div>
    );

    if (currentStep === 0) {
        return renderPromptInputs();
    }

    return (
        <div>
            <div className="prompt-top">
                {renderPromptInputs()}
            </div>

            <div className="form-check kb-view-toggle mb-3">
                <input
                    id="skip-consistency-check"
                    type="checkbox"
                    className="form-check-input"
                    checked={skipConsistencyCheck}
                    onChange={(e) => onSkipChange(e.target.checked)}
                />
                <label htmlFor="skip-consistency-check" className="form-check-label">
                    I do not request a consistency check for this run.
                </label>
            </div>

            <div className="consistency-controls">
                <div className="llm-select-wrap">
                    <label className="form-label">LLM</label>
                    <select
                        className="form-select"
                        value={selectedLlm}
                        onChange={(e) => onSelectLlm(e.target.value)}
                        disabled={llmConfigs.length === 0}
                    >
                        {llmConfigs.length === 0 ? (
                            <option value="">No LLM config found</option>
                        ) : (
                            llmConfigs.map((cfg) => (
                                <option key={cfg} value={cfg}>
                                    {cfg}
                                </option>
                            ))
                        )}
                    </select>
                </div>

                <button
                    type="button"
                    className="btn btn-primary consistency-btn"
                    onClick={onRunCheck}
                    disabled={isChecking || skipConsistencyCheck}
                >
                    {isChecking ? 'Checking...' : 'Run Consistency Check'}
                </button>
            </div>

            {skipConsistencyCheck && (
                <div className="alert alert-warning mt-3 mb-0" role="alert">
                    Consistency check skipped by user choice.
                </div>
            )}

            {llmLoadError && (
                <div className="alert alert-warning mt-3 mb-0" role="alert">
                    {llmLoadError}
                </div>
            )}

            {validationStatus && (
                <div
                    className={`alert mt-3 mb-0 ${validationStatus.type === 'success' ? 'alert-success' : 'alert-danger'}`}
                    role="alert"
                >
                    {validationStatus.message}
                </div>
            )}
        </div>
    );
};

export default PromptStep;
