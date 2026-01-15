function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
        document.cookie.split('; ')
            .find(row => row.startsWith('csrftoken='))?.split('=')[1] || '';
}

class NotificationHandler {
    static showSuccess(message, options = {}) {
        Toastify({
            text: `✅ ${message}`,
            duration: 5000,
            gravity: "top",
            position: "right",
            stopOnFocus: true,
            backgroundColor: "linear-gradient(to right, #00b09b, #96c93d)",
            ...options
        }).showToast();
    }

    static showError(message, options = {}) {
        Toastify({
            text: `❌ ${message}`,
            duration: 5000,
            gravity: "top",
            position: "right",
            stopOnFocus: true,
            backgroundColor: "linear-gradient(to right, #ff5f6d, #ffc371)",
            ...options
        }).showToast();
    }
}

const ApiClient = {
    async post({ url, data, token = null, headers = {}, isForm = true, onSuccess, onError, redirect = {} }) {
        const allHeaders = {
            "X-CSRFToken": getCSRFToken(),
            ...(isForm ? {} : { "Content-Type": "application/json" }),
            ...headers
        };

        if (token) {
            allHeaders["Authorization"] = `Bearer ${token}`;
        }

        try {
            const response = await axios.post(url, isForm ? data : JSON.stringify(data), {
                headers: allHeaders
            });

            NotificationHandler.showSuccess("Request successful!");
            if (typeof onSuccess === 'function') onSuccess(response.data);
            if (redirect.success) window.location.href = redirect.success;

        } catch (error) {
            if (error.response) {
                const status = error.response.status;
                const errData = error.response.data;

                if (typeof onError === 'function') {
                    onError(status, errData);
                } else {
                    let message = "Something went wrong.";
                    if (status === 400) message = "Validation failed.";
                    else if (status === 401) message = "Unauthorized. Please log in.";
                    else if (status === 403) message = "Access denied.";
                    else if (status === 500) message = "Server error.";
                    NotificationHandler.showError(message);
                }

                if (redirect.error) window.location.href = redirect.error;
            } else {
                NotificationHandler.showError("Unexpected error: " + error.message);
            }
        }
    },


    // PUT Method 
    
    async put({ url, data, token = null, headers = {}, isForm = true, onSuccess, onError, redirect = {} }) {
        const allHeaders = {
            "X-CSRFToken": getCSRFToken(),
            ...(isForm ? {} : { "Content-Type": "application/json" }),
            ...headers
        };

        if (token) {
            allHeaders["Authorization"] = `Bearer ${token}`;
        }

        try {
            const response = await axios.put(url, isForm ? data : JSON.stringify(data), {
                headers: allHeaders
            });

            NotificationHandler.showSuccess("Request successful!");
            if (typeof onSuccess === 'function') onSuccess(response.data);
            if (redirect.success) window.location.href = redirect.success;

        } catch (error) {
            if (error.response) {
                const status = error.response.status;
                const errData = error.response.data;

                if (typeof onError === 'function') {
                    onError(status, errData);
                } else {
                    let message = "Something went wrong.";
                    if (status === 400) message = "Validation failed.";
                    else if (status === 401) message = "Unauthorized. Please log in.";
                    else if (status === 403) message = "Access denied.";
                    else if (status === 500) message = "Server error.";
                    NotificationHandler.showError(message);
                }

                if (redirect.error) window.location.href = redirect.error;
            } else {
                NotificationHandler.showError("Unexpected error: " + error.message);
            }
        }
    }
};
  