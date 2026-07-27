// ValidationButton.jsx

import React from 'react';
import PropTypes from 'prop-types';

const ValidationButton = ({ onClick, disabled, error }) => {
    return (
        <div className="mb-4">
            <button
                className={`px-4 py-2 rounded text-white ${
                    disabled ? 'bg-gray-400 cursor-not-allowed' : 'bg-blue-500 hover:bg-blue-600'
                }`}
                onClick={onClick}
                disabled={disabled}
            >
                Validate Descriptions
            </button>
            {error && <p className="text-red-500 mt-2">{error}</p>}
        </div>
    );
};

ValidationButton.propTypes = {
    onClick: PropTypes.func.isRequired,
    disabled: PropTypes.bool,
    error: PropTypes.string,
};

ValidationButton.defaultProps = {
    disabled: false,
    error: '',
};

export default ValidationButton;
