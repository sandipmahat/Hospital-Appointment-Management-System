# ContactSaver - Event Handlers & Form Validation Documentation

## Overview

This document describes the event handling and form validation features added to the ContactSaver Flask application.

## Features Added

### 1. **Events & Alerts Module** (`events-alerts.js`)

#### Core Functions

- **`toggleVisibility(elementId)`** - Toggle element display between 'none' and 'block'
- **`showElement(elementId)`** - Show an element
- **`hideElement(elementId)`** - Hide an element

#### User Interaction

- **`showAlert(message, type)`** - Display alert dialog with type (info, success, error, warning)
- **`showConfirmation(message, onConfirm, onCancel)`** - Show confirmation dialog with callbacks
- **`showDeleteConfirmation(itemName, callback)`** - Specialized delete confirmation
- **`getUserInput(prompt, defaultValue)`** - Show prompt and get user input

#### Event Listeners

- **`attachEventListener(elementId, eventType, handler)`** - Attach any event listener
- **`attachEventListenerToClass(className, eventType, handler)`** - Attach listener to all elements with class
- **`handleClick(elementId, callback)`** - Handle click events
- **`handleSubmit(formId, callback)`** - Handle form submission
- **`handleInput(inputId, callback)`** - Handle input events
- **`handleBlur(inputId, callback)`** - Handle blur events

#### Form Utilities

- **`togglePasswordVisibility(passwordInputId, toggleButtonId)`** - Show/hide password toggle
- **`setupCharacterCounter(inputId, counterId, maxLength)`** - Real-time character counter
- **`clearForm(formId)`** - Clear all form fields
- **`setButtonEnabled(buttonId, enabled)`** - Enable/disable button with visual feedback
- **`setButtonLoading(buttonId, isLoading)`** - Show loading state on button
- **`addFocusHighlight(inputId, highlightClass)`** - Highlight input on focus

### 2. **Form Validation Module** (`form-validation.js`)

#### Validation Rules

Built-in validation rules:
- **`email`** - Validates email format using regex
- **`password`** - Validates password length (minimum 6 characters)
- **`strongPassword`** - Validates strong password (uppercase, lowercase, number, 8+ chars)
- **`required`** - Validates field is not empty
- **`name`** - Validates name (minimum 2 characters)
- **`phone`** - Validates phone number formats
- **`url`** - Validates URL format

#### Main Functions

- **`validateField(field)`** - Validate single input field
- **`validateForm(formId)`** - Validate entire form
- **`attachValidation(fieldId)`** - Attach real-time validation to field
- **`attachFormValidation(formId)`** - Attach validation to all form fields
- **`setupFormSubmission(formId, onSubmit)`** - Setup form with validation on submit

#### Error Handling

- **`showFieldError(fieldId, errorMessage)`** - Display error for field
- **`removeFieldError(fieldId)`** - Remove error for field
- **`clearFormErrors(formId)`** - Clear all form errors
- **`getFormErrors(formId)`** - Get all form errors as object

#### Password Utilities

- **`isValidEmail(email)`** - Check email validity
- **`isValidPassword(password)`** - Check password validity
- **`isStrongPassword(password)`** - Check if password is strong
- **`getPasswordStrength(password)`** - Get password strength level
- **`updatePasswordStrength(passwordInputId, strengthIndicatorId)`** - Show strength indicator
- **`validatePasswordMatch(passwordFieldId, confirmFieldId)`** - Validate matching passwords

#### Custom Validation

- **`registerValidationRule(ruleName, validateFunction, errorMessage)`** - Register custom validation rule

## Usage Examples

### Registration Form

```html
<form id="registrationForm" method="post">
    <div class="form-group">
        <label for="email">Email</label>
        <input type="email" id="email" name="email" 
               data-validate="required,email">
    </div>
    <div class="form-group">
        <label for="password">Password</label>
        <input type="password" id="password" name="password" 
               data-validate="required,password">
    </div>
</form>

<script>
    document.addEventListener('DOMContentLoaded', function() {
        // Attach validation to all fields
        attachFormValidation('registrationForm');
        
        // Show password strength indicator
        updatePasswordStrength('password', 'passwordStrength');
        
        // Setup form submission with validation
        setupFormSubmission('registrationForm', function(form) {
            showAlert('Registration successful!', 'success');
            form.submit();
        });
    });
</script>
```

### Delete Confirmation

```javascript
// In HTML
<button onclick="deleteContact(this, 'John Doe')">Delete</button>

// In JavaScript
function deleteContact(button, contactName) {
    showDeleteConfirmation(contactName, function() {
        // Handle deletion
        button.closest('.contact-item').remove();
        showAlert(`${contactName} deleted successfully.`, 'success');
    });
}
```

### Character Counter

```javascript
setupCharacterCounter('inputId', 'counterId', 500);
// Shows: "45/500 characters"
```

### Password Toggle

```javascript
togglePasswordVisibility('password', 'togglePasswordBtn');
// Clicking button toggles between password and text input
```

## HTML Attributes

Use `data-validate` attribute to specify validation rules for inputs:

```html
<!-- Single rule -->
<input data-validate="email">

<!-- Multiple rules (comma-separated) -->
<input data-validate="required,email">

<!-- Custom validation -->
<input data-validate="required" data-customValidation="myCustomValidator">
```

## CSS Classes Used

- **`.error`** - Applied to input when validation fails
- **`.error-message`** - Error message element
- **`.password-strength`** - Password strength indicator
- **`.focused`** - Applied to focused input
- **`.char-counter`** - Character counter display

## Implementation in Templates

### Login Template
- Email validation
- Password visibility toggle
- Real-time validation
- Remember me checkbox

### Registration Template
- Full name validation (min 2 chars)
- Email validation
- Password validation (min 6 chars)
- Password strength indicator
- Password match validation
- Character counter for name
- Clear form button

### Contact Template
- Contact name validation
- Email validation
- Message validation
- Delete confirmation dialog
- Real-time contact list updates
- Character counter for message

## Error Messages

All validation errors are displayed dynamically:
- Red border on invalid fields
- Error message appears below field
- Auto-hide when field is corrected
- Smooth animations for UX

## Accessibility Features

- Keyboard navigation support
- Focus indicators (visible outlines)
- Proper label associations
- ARIA-compatible structure
- Clear error messages

## Browser Compatibility

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+
- Works with modern JavaScript (ES6)

## Notes

- All validation happens client-side; implement server-side validation as well
- Use `preventDefault()` to prevent form submission on validation errors
- Chain multiple functions for complex validation scenarios
- Custom validation rules can be registered using `registerValidationRule()`
