# Quick Reference Guide - Events & Alerts + Form Validation

## File Locations

```
apps/
├── static/
│   ├── js/
│   │   ├── events-alerts.js      # Event handling & user interaction
│   │   └── form-validation.js    # Form validation logic
│   └── css/
│       └── style.css             # Includes validation styles
└── templates/
    ├── base.html                 # Includes JavaScript modules
    ├── login.html                # Validated login form
    ├── register.html             # Validated registration form
    └── contact.html              # Contact management with delete confirmation
```

## Quick Code Snippets

### Validate Form Before Submission
```javascript
if (validateForm('myForm')) {
    // Form is valid, submit
    document.getElementById('myForm').submit();
}
```

### Show Delete Confirmation
```javascript
showDeleteConfirmation('Item Name', function() {
    // Item deleted - handle deletion here
});
```

### Real-Time Email Validation
```html
<input type="email" id="email" data-validate="required,email">
<script>
    attachValidation('email');
</script>
```

### Get Password Strength
```javascript
const strength = getPasswordStrength('MyPassword123');
// Returns: 'weak', 'medium', or 'strong'
```

### Toggle Element Visibility
```javascript
toggleVisibility('elementId');
```

### Clear Form & Errors
```javascript
clearForm('myForm');
clearFormErrors('myForm');
```

### Show Alert
```javascript
showAlert('Message here', 'success');  // success, error, info
```

### Character Counter
```html
<input id="message" type="text">
<span id="counter"></span>
<script>
    setupCharacterCounter('message', 'counter', 500);
</script>
```

### Prevent Form Submit on Enter
```javascript
preventSubmitOnEnter('inputId');
```

## Validation Data Attributes

```html
<!-- Single validation -->
<input data-validate="email">

<!-- Multiple validations -->
<input data-validate="required,email,password">

<!-- Available rules: email, password, strongPassword, required, name, phone, url -->
```

## Common Patterns

### Complete Form Setup
```javascript
document.addEventListener('DOMContentLoaded', function() {
    // 1. Attach validation to all fields
    attachFormValidation('myForm');
    
    // 2. Setup special features
    togglePasswordVisibility('password', 'toggleBtn');
    updatePasswordStrength('password', 'strengthIndicator');
    
    // 3. Setup submission
    setupFormSubmission('myForm', function(form) {
        showAlert('Success!', 'success');
        form.submit();
    });
});
```

### Add Delete Button Handler
```javascript
button.addEventListener('click', function() {
    showDeleteConfirmation('Item Name', function() {
        // Delete logic here
        button.closest('.item').remove();
    });
});
```

## Validation Error Messages

| Rule | Message |
|------|---------|
| `required` | This field is required |
| `email` | Please enter a valid email address |
| `password` | Password must be at least 6 characters long |
| `strongPassword` | Password must contain uppercase, lowercase, number, and be at least 8 characters |
| `name` | Name must be at least 2 characters long |
| `phone` | Please enter a valid phone number |
| `url` | Please enter a valid URL |

## CSS Classes for Styling

```css
input.error { }              /* Invalid input */
input.focused { }            /* Focused input */
input.success { }            /* Valid input */

.error-message { }           /* Error text */
.password-strength { }       /* Strength indicator */
.char-counter { }            /* Character count */
.confirmation-dialog { }     /* Confirmation dialog */
```

## Advanced Usage

### Custom Validation Rule
```javascript
registerValidationRule('customRule', 
    function(value) {
        return value.length > 5;  // Return true if valid
    },
    'Custom error message here'
);

// Then use:
// <input data-validate="customRule">
```

### Custom Validator Function
```javascript
// Define function
function myValidator(value) {
    if (value.includes('bad')) {
        return 'Value cannot contain "bad"';
    }
    return null;  // null means valid
}

// Use with data attribute
// <input data-customValidation="myValidator">
```

### Get All Form Errors
```javascript
const errors = getFormErrors('myForm');
// Returns: { fieldName: 'Error message', ... }

for (let field in errors) {
    console.log(`${field}: ${errors[field]}`);
}
```

## Testing Validation

### Test Email
```javascript
isValidEmail('user@example.com');  // true
isValidEmail('invalid.email');     // false
```

### Test Password
```javascript
isValidPassword('short');           // false
isValidPassword('password123');     // true
isStrongPassword('Strong@Pass1');   // true
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Tab` | Navigate between fields |
| `Enter` | Submit form (if not prevented) |
| `Shift+Tab` | Navigate backwards |

## Tips & Tricks

1. **Combine validation functions** - Use multiple validators together
2. **Show success states** - Add `.success` class to validated fields
3. **Animate errors** - Errors slide down smoothly (built-in animation)
4. **Mobile friendly** - All features work on touch devices
5. **Accessibility** - Form handles keyboard navigation automatically

## Debugging

### Check if field has validation
```javascript
console.log(document.getElementById('fieldId').dataset.validate);
```

### Manually trigger validation
```javascript
const error = validateField(document.getElementById('fieldId'));
if (error) {
    showFieldError('fieldId', error);
}
```

### See all form errors
```javascript
console.log(getFormErrors('myForm'));
```
