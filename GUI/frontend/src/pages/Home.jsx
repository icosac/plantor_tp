import React from 'react';
import './home.css';
import WorkflowProgress from './workflow/components/WorkflowProgress';
import WorkflowStepContent from './workflow/components/WorkflowStepContent';
import WorkflowNavigation from './workflow/components/WorkflowNavigation';
import useWorkflowController from './workflow/hooks/useWorkflowController';

const Home = () => {
    const {
        steps,
        currentStep,
        stepName,
        progress,
        canProceedCurrentStep,
        canAccessStep,
        goToStep,
        moveStep,
        promptStepProps,
        kbGenerationStepProps,
        planningStepProps,
        enablersStepProps,
        optimizedStnStepProps,
        btStepProps,
    } = useWorkflowController();

    return (
        <div className="workflow-page">
            <WorkflowProgress
                steps={steps}
                currentStep={currentStep}
                progress={progress}
                canAccessStep={canAccessStep}
                onStepSelect={goToStep}
            />

            <section className="card shadow-sm">
                <div className="card-header bg-primary text-white">
                    {stepName}
                </div>
                <div className="card-body">
                    <WorkflowStepContent
                        currentStep={currentStep}
                        stepName={stepName}
                        promptStepProps={promptStepProps}
                        kbGenerationStepProps={kbGenerationStepProps}
                        planningStepProps={planningStepProps}
                        enablersStepProps={enablersStepProps}
                        optimizedStnStepProps={optimizedStnStepProps}
                        btStepProps={btStepProps}
                    />
                </div>

                <WorkflowNavigation
                    onPrevious={() => moveStep(-1)}
                    onNext={() => moveStep(1)}
                    disablePrevious={currentStep === 0}
                    disableNext={currentStep === steps.length - 1 || !canProceedCurrentStep}
                    isLastStep={currentStep === steps.length - 1}
                />
            </section>
        </div>
    );
};

export default Home;
