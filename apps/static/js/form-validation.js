/**
 * Form Validation Module
 * Handles form field validation and error messages
 */

// Email validation regex
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Password strength regex (at least one uppercase, one lowercase, one number)
const STRONG_PASSWORD_REGEX = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/;

// Validation rules object
const validationRules = {
    email: {
        validate: (value) => EMAIL_REGEX.test(value),
        errorMessage: 'Please enter a valid email address'
    },
    password: {
        validate: (value) => value.length >= 6,
        errorMessage: 'Password must be at least 6 characters long'
    },
    strongPassword: {
        validate: (value) => STRONG_PASSWORD_REGEX.test(value),
        errorMessage: 'Password must contain uppercase, lowercase, number, and be at least 8 characters'
    },
    required: {
        validate: (value) => value.trim().length > 0,
        errorMessage: 'This field is required'
    },
    name: {
        validate: (value) => value.trim().length >= 2,
        errorMessage: 'Name must be at least 2 characters long'
    },
    phone: {
        validate: (value) => /^\d{10}$|^\d{3}-\d{3}-\d{4}$|^\(\d{3}\)\s\d{3}-\d{4}$/.test(value),
        errorMessage: 'Please enter a valid phone number'
    },
    url: {
        validate: (value) => /^https?:\/\/.+\..+$/.test(value),
        errorMessage: 'Please enter a valid URL'
    }
};

// Get all form errors
function getFormErrors(formId) {
    const form = document.getElementById(formId);
    const errors = {};
    
    if (!form) {
        console.warn(`Form with ID "${formId}" not found`);
        return errors;
    }
    
    const inputs = form.querySelectorAll('input, textarea, select');
    inputs.forEach(input => {
        const error = validateField(input);
        if (error) {
            errors[input.name] = error;
        }
    });
    
    return errors;
}

// Validate a single field
function validateField(field) {
    if (!field) return null;
    
    const value = field.value;
    const rules = field.dataset.validate ? field.dataset.validate.split(',') : [];
    const customRule = field.dataset.customValidation;
    
    // Check required rule
    if (rules.includes('required')) {
        if (!validationRules.required.validate(value)) {
            return validationRules.required.errorMessage;
        }
    }
    
    // Skip further validation if field is empty and not required
    if (!rules.includes('required') && value.trim() === '') {
        return null;
    }
    
    // Check other rules
    for (let rule of rules) {
        if (validationRules[rule] && !validationRules[rule].validate(value)) {
            return validationRules[rule].errorMessage;
        }
    }
    
    // Check custom validation function
    if (customRule && typeof window[customRule] === 'function') {
        const customError = window[customRule](value);
        if (customError) {
            return customError;
        }
    }
    
    return null;
}

// Display error message
function showFieldError(fieldId, errorMessage) {
    const field = document.getElementById(fieldId);
    if (!field) return false;
    
    // Remove existing error
    removeFieldError(fieldId);
    
    // Add error class to field
    field.classList.add('error');
    
    // Create and append error message
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.id = `${fieldId}-error`;
    errorDiv.setAttribute('role', 'alert');
    errorDiv.setAttribute('aria-live', 'polite');
    errorDiv.textContent = errorMessage;
    
    field.insertAdjacentElement('afterend', errorDiv);
    return true;
}

// Remove error message
function removeFieldError(fieldId) {
    const field = document.getElementById(fieldId);
    if (!field) return false;
    
    field.classList.remove('error');
    
    const errorDiv = document.getElementById(`${fieldId}-error`);
    if (errorDiv) {
        errorDiv.remove();
    }
    
    return true;
}

// Clear all errors in form
function clearFormErrors(formId) {
    const form = document.getElementById(formId);
    if (!form) return false;
    
    const errorMessages = form.querySelectorAll('.error-message');
    errorMessages.forEach(msg => msg.remove());
    
    const errorFields = form.querySelectorAll('.error');
    errorFields.forEach(field => field.classList.remove('error'));
    
    return true;
}

// Validate entire form
function validateForm(formId) {
    clearFormErrors(formId);
    const errors = getFormErrors(formId);
    
    if (Object.keys(errors).length === 0) {
        return true;
    }
    
    // Display errors
    for (let fieldName in errors) {
        const field = document.querySelector(`#${formId} [name="${fieldName}"]`);
        if (field) {
            showFieldError(field.id, errors[fieldName]);
        }
    }
    
    return false;
}

// Real-time field validation
function attachValidation(fieldId) {
    const field = document.getElementById(fieldId);
    if (!field) return false;
    
    field.addEventListener('blur', function() {
        const error = validateField(this);
        if (error) {
            showFieldError(fieldId, error);
        } else {
            removeFieldError(fieldId);
        }
    });
    
    field.addEventListener('input', function() {
        const error = validateField(this);
        if (!error) {
            removeFieldError(fieldId);
        }
    });
    
    return true;
}

// Attach validation to all fields in a form
function attachFormValidation(formId) {
    const form = document.getElementById(formId);
    if (!form) return false;
    
    const inputs = form.querySelectorAll('input, textarea, select');
    inputs.forEach(input => {
        attachValidation(input.id);
    });
    
    return true;
}

// Setup form submission with validation
function setupFormSubmission(formId, onSubmit) {
    const form = document.getElementById(formId);
    if (!form) return false;
    
    form.addEventListener('submit', function(event) {
        event.preventDefault();
        
        if (validateForm(formId)) {
            if (typeof onSubmit === 'function') {
                onSubmit(this);
            }
        }
    });
    
    return true;
}

// Check if email is valid
function isValidEmail(email) {
    return validationRules.email.validate(email);
}

// Check if password is valid
function isValidPassword(password) {
    return validationRules.password.validate(password);
}

// Check if password is strong
function isStrongPassword(password) {
    return validationRules.strongPassword.validate(password);
}

// Get password strength level
function getPasswordStrength(password) {
    if (password.length < 6) return 'weak';
    if (STRONG_PASSWORD_REGEX.test(password)) return 'strong';
    return 'medium';
}

// Update password strength indicator
function updatePasswordStrength(passwordInputId, strengthIndicatorId) {
    const input = document.getElementById(passwordInputId);
    const indicator = document.getElementById(strengthIndicatorId);
    
    if (!input || !indicator) return false;
    
    input.addEventListener('input', function() {
        const strength = getPasswordStrength(this.value);
        indicator.className = `password-strength ${strength}`;
        
        let text = '';
        let color = '';
        switch(strength) {
            case 'weak':
                text = 'Weak';
                color = '#d32f2f';
                break;
            case 'medium':
                text = 'Medium';
                color = '#f57c00';
                break;
            case 'strong':
                text = 'Strong';
                color = '#388e3c';
                break;
        }
        
        indicator.textContent = text;
        indicator.style.color = color;
    });
    
    return true;
}

// Custom validation example: match password fields
function validatePasswordMatch(passwordFieldId, confirmFieldId) {
    const passwordField = document.getElementById(passwordFieldId);
    const confirmField = document.getElementById(confirmFieldId);
    
    if (!passwordField || !confirmField) return false;
    
    function validateMatch() {
        if (confirmField.value !== passwordField.value) {
            showFieldError(confirmFieldId, 'Passwords do not match');
        } else {
            removeFieldError(confirmFieldId);
        }
    }

    confirmField.addEventListener('blur', validateMatch);
    confirmField.addEventListener('input', validateMatch);
    passwordField.addEventListener('input', validateMatch);
    
    return true;
}

// Register custom validation rule
function registerValidationRule(ruleName, validateFunction, errorMessage) {
    validationRules[ruleName] = {
        validate: validateFunction,
        errorMessage: errorMessage
    };
}

// Export functions for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        EMAIL_REGEX,
        STRONG_PASSWORD_REGEX,
        validationRules,
        getFormErrors,
        validateField,
        showFieldError,
        removeFieldError,
        clearFormErrors,
        validateForm,
        attachValidation,
        attachFormValidation,
        setupFormSubmission,
        isValidEmail,
        isValidPassword,
        isStrongPassword,
        getPasswordStrength,
        updatePasswordStrength,
        validatePasswordMatch,
        registerValidationRule
    };
}
