/**
 * Events and Alerts Module
 * Handles event listeners, user interactions, and confirmation dialogs
 */

// Toggle element visibility
function toggleVisibility(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.style.display = element.style.display === 'none' ? 'block' : 'none';
    }
}

// Show element
function showElement(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.style.display = 'block';
    }
}

// Hide element
function hideElement(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.style.display = 'none';
    }
}

// Delete confirmation dialog
function showDeleteConfirmation(itemName, callback) {
    const confirmed = confirm(`Are you sure you want to delete "${itemName}"? This action cannot be undone.`);
    if (confirmed) {
        if (typeof callback === 'function') {
            callback();
        }
    }
    return confirmed;
}

// Generic confirmation dialog
function showConfirmation(message, onConfirm, onCancel) {
    const confirmed = confirm(message);
    if (confirmed && typeof onConfirm === 'function') {
        onConfirm();
    } else if (!confirmed && typeof onCancel === 'function') {
        onCancel();
    }
    return confirmed;
}

// Show alert message
function showAlert(message, type = 'info') {
    alert(`[${type.toUpperCase()}] ${message}`);
}

// Show prompt and get user input
function getUserInput(prompt, defaultValue = '') {
    return prompt(prompt, defaultValue);
}

// Attach event listener with error handling
function attachEventListener(elementId, eventType, handler) {
    const element = document.getElementById(elementId);
    if (element) {
        element.addEventListener(eventType, handler);
        return true;
    } else {
        console.warn(`Element with ID "${elementId}" not found`);
        return false;
    }
}

// Attach event listeners to all elements with a specific class
function attachEventListenerToClass(className, eventType, handler) {
    const elements = document.querySelectorAll(`.${className}`);
    elements.forEach(element => {
        element.addEventListener(eventType, handler);
    });
    return elements.length;
}

// Handle click events
function handleClick(elementId, callback) {
    return attachEventListener(elementId, 'click', callback);
}

// Handle submit events
function handleSubmit(formId, callback) {
    return attachEventListener(formId, 'submit', callback);
}

// Handle input events
function handleInput(inputId, callback) {
    return attachEventListener(inputId, 'input', callback);
}

// Handle blur events (when input loses focus)
function handleBlur(inputId, callback) {
    return attachEventListener(inputId, 'blur', callback);
}

// Real-time character counter for input fields
function setupCharacterCounter(inputId, counterId, maxLength = null) {
    const input = document.getElementById(inputId);
    const counter = document.getElementById(counterId);
    
    if (input && counter) {
        input.addEventListener('input', function() {
            const length = this.value.length;
            counter.textContent = `${length}${maxLength ? `/${maxLength}` : ''} characters`;
        });
        return true;
    }
    return false;
}

// Toggle password visibility
function togglePasswordVisibility(passwordInputId, toggleButtonId) {
    const passwordInput = document.getElementById(passwordInputId);
    const toggleButton = document.getElementById(toggleButtonId);
    
    if (passwordInput && toggleButton) {
        toggleButton.addEventListener('click', function() {
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);
            this.textContent = type === 'password' ? '👁️ Show' : '🔒 Hide';
        });
        return true;
    }
    return false;
}

// Prevent form submission on Enter key in specific input
function preventSubmitOnEnter(inputId) {
    const input = document.getElementById(inputId);
    if (input) {
        input.addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                return false;
            }
        });
        return true;
    }
    return false;
}

// Add focus event to highlight input
function addFocusHighlight(inputId, highlightClass = 'focused') {
    const input = document.getElementById(inputId);
    if (input) {
        input.addEventListener('focus', function() {
            this.classList.add(highlightClass);
        });
        input.addEventListener('blur', function() {
            this.classList.remove(highlightClass);
        });
        return true;
    }
    return false;
}

// Clear form fields
function clearForm(formId) {
    const form = document.getElementById(formId);
    if (form) {
        form.reset();
        return true;
    }
    return false;
}

// Disable/Enable button
function setButtonEnabled(buttonId, enabled = true) {
    const button = document.getElementById(buttonId);
    if (button) {
        button.disabled = !enabled;
        button.style.opacity = enabled ? '1' : '0.5';
        button.style.cursor = enabled ? 'pointer' : 'not-allowed';
        return true;
    }
    return false;
}

// Show loading state on button
function setButtonLoading(buttonId, isLoading = true) {
    const button = document.getElementById(buttonId);
    if (button) {
        if (isLoading) {
            button.dataset.originalText = button.textContent;
            button.textContent = '⏳ Loading...';
            button.disabled = true;
        } else {
            button.textContent = button.dataset.originalText || 'Submit';
            button.disabled = false;
        }
        return true;
    }
    return false;
}

// Export functions for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        toggleVisibility,
        showElement,
        hideElement,
        showDeleteConfirmation,
        showConfirmation,
        showAlert,
        getUserInput,
        attachEventListener,
        attachEventListenerToClass,
        handleClick,
        handleSubmit,
        handleInput,
        handleBlur,
        setupCharacterCounter,
        togglePasswordVisibility,
        preventSubmitOnEnter,
        addFocusHighlight,
        clearForm,
        setButtonEnabled,
        setButtonLoading
    };
}
