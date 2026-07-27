// ActionButton.jsx

import React from 'react';
import PropTypes from 'prop-types';

const ActionButton = ({ label, onClick, disabled }) => {
    return (
        <div className="mb-4">
            <button
                className={`px-4 py-2 rounded text-white font-medium ${
                    disabled ? 'bg-gray-400 cursor-not-allowed' : 'bg-green-500 hover:bg-green-600'
                }`}
                onClick={onClick}
                disabled={disabled}
            >
                {label}
            </button>
        </div>
    );
};

ActionButton.propTypes = {
    label: PropTypes.string.isRequired,
    onClick: PropTypes.func.isRequired,
    disabled: PropTypes.bool,
};

ActionButton.defaultProps = {
    disabled: false,
};

export default ActionButton;
