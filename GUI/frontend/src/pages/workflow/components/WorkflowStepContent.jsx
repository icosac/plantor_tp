import React from 'react';
import PromptStep from '../../steps/PromptStep';
import KBGenerationStep from '../../steps/KBGenerationStep';
import PlanningStep from '../../steps/PlanningStep';
import EnablersStep from '../../steps/EnablersStep';
import OptimizedSTNStep from '../../steps/OptimizedSTNStep';
import BTStep from '../../steps/BTStep';

const WorkflowStepContent = ({
    currentStep,
    stepName,
    promptStepProps,
    kbGenerationStepProps,
    planningStepProps,
    enablersStepProps,
    optimizedStnStepProps,
    btStepProps,
}) => {
    if (currentStep <= 1) {
        return <PromptStep {...promptStepProps} />;
    }

    if (currentStep <= 3) {
        return <KBGenerationStep {...kbGenerationStepProps} />;
    }

    if (currentStep <= 5) {
        return <PlanningStep currentStep={currentStep} stepName={stepName} {...planningStepProps} />;
    }

    if (currentStep === 6) {
        return <EnablersStep stepName={stepName} {...enablersStepProps} />;
    }

    if (currentStep === 7) {
        return <OptimizedSTNStep stepName={stepName} {...optimizedStnStepProps} />;
    }

    return <BTStep stepName={stepName} {...btStepProps} />;
};

export default WorkflowStepContent;
