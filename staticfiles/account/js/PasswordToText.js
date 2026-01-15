document.querySelectorAll('.toggle-password').forEach(icon => {
    icon.addEventListener('click', function () {
        const passwordField = this.previousElementSibling;
        if (passwordField.type === 'password') {
            passwordField.type = 'text';
            this.classList.replace('fa-eye', 'fa-eye-slash');
        } else {
            passwordField.type = 'password';
            this.classList.replace('fa-eye-slash', 'fa-eye');
        }
    });
});