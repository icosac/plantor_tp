import React from 'react';

const KBGenerationStep = ({
    currentStep,
    highLevelDesc,
    lowLevelDesc,
    onHighLevelChange,
    onLowLevelChange,
    llmConfigs,
    selectedLlm,
    onSelectLlm,
    llmLoadError,
    onAutoResize,
    MIN_VERIFY_RETRY_BUDGET,
    parseRetryBudget,
    isGeneratingHlKb,
    hlGenerationStatus,
    verifyHlGeneration,
    onVerifyHlChange,
    verifyHlRetries,
    onVerifyHlRetriesChange,
    hlCombinedView,
    onHlCombinedToggle,
    hlCombinedContent,
    onHlCombinedChange,
    hlKbContent,
    onHlKbChange,
    hlInitContent,
    onHlInitChange,
    hlGoalContent,
    onHlGoalChange,
    hlActionsContent,
    onHlActionsChange,
    onRunHlGeneration,
    onDownloadHlKb,
    isGeneratingLlKb,
    llGenerationStatus,
    verifyLlGeneration,
    onVerifyLlChange,
    verifyLlRetries,
    onVerifyLlRetriesChange,
    skipLlGeneration,
    onSkipLlGenerationChange,
    llCombinedView,
    onLlCombinedToggle,
    llCombinedContent,
    onLlCombinedChange,
    llKbContent,
    onLlKbChange,
    llInitContent,
    onLlInitChange,
    llGoalContent,
    onLlGoalChange,
    llActionsContent,
    onLlActionsChange,
    llMappingsContent,
    onLlMappingsChange,
    onRunLlGeneration,
    onDownloadLlKb,
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

    const renderSectionEditor = (label, value, onChange, placeholder) => (
        <div className="col-md-6">
            <div className="kb-output mb-3">
                <label className="form-label fw-semibold">{label}</label>
                <textarea
                    className="form-control kb-editor auto-resize"
                    rows="8"
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    onInput={onAutoResize}
                    placeholder={placeholder}
                ></textarea>
            </div>
        </div>
    );

    if (currentStep === 2) {
        return (
            <div>
                <div className="prompt-top">
                    {renderPromptInputs()}
                </div>

                <div className="form-check kb-view-toggle mb-3">
                    <input
                        id="hl-combined-view"
                        type="checkbox"
                        className="form-check-input"
                        checked={hlCombinedView}
                        onChange={(e) => onHlCombinedToggle(e.target.checked)}
                    />
                    <label htmlFor="hl-combined-view" className="form-check-label">
                        Show HL output as a single textarea
                    </label>
                </div>

                <div className="form-check kb-view-toggle verification-toggle mb-3">
                    <input
                        id="hl-verify-generation"
                        type="checkbox"
                        className="form-check-input"
                        checked={verifyHlGeneration}
                        onChange={(e) => onVerifyHlChange(e.target.checked)}
                    />
                    <label htmlFor="hl-verify-generation" className="form-check-label">
                        Enable automatic HL consistency verification after generation.
                    </label>
                    {verifyHlGeneration && (
                        <div className="verify-retries-row">
                            <label htmlFor="hl-verify-retries" className="verify-retries-label">
                                Number of iterations
                            </label>
                            <input
                                id="hl-verify-retries"
                                type="number"
                                className="form-control form-control-sm verify-retries-input"
                                min={MIN_VERIFY_RETRY_BUDGET}
                                step="1"
                                value={verifyHlRetries}
                                onChange={(e) => onVerifyHlRetriesChange(parseRetryBudget(e.target.value, MIN_VERIFY_RETRY_BUDGET))}
                            />
                        </div>
                    )}
                    <div className="verify-cost-note">
                        This will use more tokens and may increase costs.
                    </div>
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
                        onClick={onRunHlGeneration}
                        disabled={isGeneratingHlKb}
                    >
                        {isGeneratingHlKb ? 'Generating...' : 'Generate HL KB'}
                    </button>
                    <button
                        type="button"
                        className="btn btn-outline-secondary consistency-btn"
                        onClick={onDownloadHlKb}
                        disabled={isGeneratingHlKb || !hlKbContent.trim()}
                    >
                        Download .pl
                    </button>
                </div>

                {llmLoadError && (
                    <div className="alert alert-warning mt-3 mb-0" role="alert">
                        {llmLoadError}
                    </div>
                )}

                {hlGenerationStatus && (
                    <div
                        className={`alert mt-3 mb-0 ${hlGenerationStatus.type === 'success' ? 'alert-success' : 'alert-danger'}`}
                        role="alert"
                    >
                        {hlGenerationStatus.message}
                    </div>
                )}

                {hlCombinedView ? (
                    <div className="kb-output mt-3">
                        <label className="form-label fw-semibold">HL Combined</label>
                        <textarea
                            className="form-control kb-editor auto-resize"
                            rows="12"
                            value={hlCombinedContent}
                            onChange={(e) => onHlCombinedChange(e.target.value)}
                            onInput={onAutoResize}
                            placeholder="Generated HL kb/init/goal/actions will appear here."
                        ></textarea>
                    </div>
                ) : (
                    <div className="row mt-3">
                        {renderSectionEditor('HL KB', hlKbContent, onHlKbChange, 'Generated HL kb section will appear here.')}
                        {renderSectionEditor('HL Init', hlInitContent, onHlInitChange, 'Generated HL init section will appear here.')}
                        {renderSectionEditor('HL Goal', hlGoalContent, onHlGoalChange, 'Generated HL goal section will appear here.')}
                        {renderSectionEditor('HL Actions', hlActionsContent, onHlActionsChange, 'Generated HL actions section will appear here.')}
                    </div>
                )}
            </div>
        );
    }

    return (
        <div>
            <div className="form-check kb-view-toggle mb-3">
                <input
                    id="skip-ll-generation"
                    type="checkbox"
                    className="form-check-input"
                    checked={skipLlGeneration}
                    onChange={(e) => onSkipLlGenerationChange(e.target.checked)}
                />
                <label htmlFor="skip-ll-generation" className="form-check-label">
                    I do not need a low-level generation.
                </label>
            </div>

            {skipLlGeneration && (
                <div className="alert alert-warning mt-3 mb-0" role="alert">
                    Low-level KB generation skipped by user choice. You can proceed to Planning.
                </div>
            )}

            {!skipLlGeneration && (
                <>
                    <div className="form-check kb-view-toggle mb-3">
                        <input
                            id="ll-combined-view"
                            type="checkbox"
                            className="form-check-input"
                            checked={llCombinedView}
                            onChange={(e) => onLlCombinedToggle(e.target.checked)}
                        />
                        <label htmlFor="ll-combined-view" className="form-check-label">
                            Show LL output as a single textarea
                        </label>
                    </div>

                    <div className="form-check kb-view-toggle verification-toggle mb-3">
                        <input
                            id="ll-verify-generation"
                            type="checkbox"
                            className="form-check-input"
                            checked={verifyLlGeneration}
                            onChange={(e) => onVerifyLlChange(e.target.checked)}
                        />
                        <label htmlFor="ll-verify-generation" className="form-check-label">
                            Enable automatic LL consistency verification after generation.
                        </label>
                        {verifyLlGeneration && (
                            <div className="verify-retries-row">
                                <label htmlFor="ll-verify-retries" className="verify-retries-label">
                                    Number of iterations
                                </label>
                                <input
                                    id="ll-verify-retries"
                                    type="number"
                                    className="form-control form-control-sm verify-retries-input"
                                    min={MIN_VERIFY_RETRY_BUDGET}
                                    step="1"
                                    value={verifyLlRetries}
                                    onChange={(e) => onVerifyLlRetriesChange(parseRetryBudget(e.target.value, MIN_VERIFY_RETRY_BUDGET))}
                                />
                            </div>
                        )}
                        <div className="verify-cost-note">
                            This will use more tokens and may increase costs.
                        </div>
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
                            onClick={onRunLlGeneration}
                            disabled={isGeneratingLlKb || skipLlGeneration}
                        >
                            {isGeneratingLlKb ? 'Generating...' : 'Generate LL KB'}
                        </button>
                        <button
                            type="button"
                            className="btn btn-outline-secondary consistency-btn"
                            onClick={onDownloadLlKb}
                            disabled={isGeneratingLlKb || !llKbContent.trim()}
                        >
                            Download .pl
                        </button>
                    </div>

                    {llmLoadError && (
                        <div className="alert alert-warning mt-3 mb-0" role="alert">
                            {llmLoadError}
                        </div>
                    )}

                    {llGenerationStatus && (
                        <div
                            className={`alert mt-3 mb-0 ${llGenerationStatus.type === 'success' ? 'alert-success' : 'alert-danger'}`}
                            role="alert"
                        >
                            {llGenerationStatus.message}
                        </div>
                    )}

                    <div className="alert alert-info mt-3 mb-0" role="alert">
                        LL generation uses the current HL content from the previous step, including user edits.
                    </div>

                    {llCombinedView ? (
                        <div className="kb-output mt-3">
                            <label className="form-label fw-semibold">LL Combined</label>
                            <textarea
                                className="form-control kb-editor auto-resize"
                                rows="12"
                                value={llCombinedContent}
                                onChange={(e) => onLlCombinedChange(e.target.value)}
                                onInput={onAutoResize}
                                placeholder="Generated LL kb/init/goal/ll_actions/mappings will appear here."
                            ></textarea>
                        </div>
                    ) : (
                        <div className="row mt-3">
                            {renderSectionEditor('LL KB', llKbContent, onLlKbChange, 'Generated LL kb section will appear here.')}
                            {renderSectionEditor('LL Init', llInitContent, onLlInitChange, 'Generated LL init section will appear here.')}
                            {renderSectionEditor('LL Goal', llGoalContent, onLlGoalChange, 'Generated LL goal section will appear here.')}
                            {renderSectionEditor('LL Actions', llActionsContent, onLlActionsChange, 'Generated LL actions section will appear here.')}
                            {renderSectionEditor('LL Mappings', llMappingsContent, onLlMappingsChange, 'Generated LL mappings section will appear here.')}
                        </div>
                    )}
                </>
            )}
        </div>
    );
};

export default KBGenerationStep;
