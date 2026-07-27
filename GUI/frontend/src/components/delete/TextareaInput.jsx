// TextareaInput.jsx

import React from 'react';
import PropTypes from 'prop-types';

const TextareaInput = ({ label, value, onChange, placeholder }) => {
    return (
        <div className="mb-3">
            <label className="form-label">{label}</label>
            <textarea
                className="form-control"
                rows="6"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder={placeholder}
            />
        </div>
    );
};

TextareaInput.propTypes = {
    label: PropTypes.string.isRequired,
    value: PropTypes.string.isRequired,
    onChange: PropTypes.func.isRequired,
    placeholder: PropTypes.string,
};

TextareaInput.defaultProps = {
    placeholder: '',
};

export default TextareaInput;
