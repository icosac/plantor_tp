import React from 'react';

const WorkflowNavigation = ({
    onPrevious,
    onNext,
    disablePrevious,
    disableNext,
    isLastStep,
}) => (
    <div className="card-footer d-flex justify-content-between">
        <button
            type="button"
            className="btn btn-outline-secondary"
            onClick={onPrevious}
            disabled={disablePrevious}
        >
            Previous
        </button>
        {isLastStep ? (
            <span className="align-self-center fw-semibold text-success">The end!</span>
        ) : (
            <button
                type="button"
                className="btn btn-primary"
                onClick={onNext}
                disabled={disableNext}
            >
                Next
            </button>
        )}
    </div>
);

export default WorkflowNavigation;
