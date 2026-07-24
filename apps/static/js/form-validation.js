/**
 * Form Validation Module
 * Real-time field validation used by the login and profile forms
 * (data-validate="required,email" / "required,name" / "required" attributes).
 */

// Email validation regex
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Validation rules object
const validationRules = {
    email: {
        validate: (value) => EMAIL_REGEX.test(value),
        errorMessage: 'Please enter a valid email address'
    },
    required: {
        validate: (value) => value.trim().length > 0,
        errorMessage: 'This field is required'
    },
    name: {
        validate: (value) => value.trim().length >= 2,
        errorMessage: 'Name must be at least 2 characters long'
    }
};

// Validate a single field
function validateField(field) {
    if (!field) return null;

    const value = field.value;
    const rules = field.dataset.validate ? field.dataset.validate.split(',') : [];

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
