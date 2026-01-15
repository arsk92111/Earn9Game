function getCSRFTokenGet() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
        document.cookie.split('; ')
            .find(row => row.startsWith('csrftoken='))?.split('=')[1] || '';
}

class NotificationHandlerGet {
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

const ApiClientGet = { 
    async get({ url, token = null, headers = {}, onSuccess, onError, redirect = {} }) {
        const allHeaders = {
            "X-CSRFToken": getCSRFTokenGet(),
            ...headers
        };

        if (token) {
            allHeaders["Authorization"] = `Bearer ${token}`;
        }

        try {
            const response = await axios.get(url, { headers: allHeaders });
 
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
                    if (status === 400) message = "Bad Request.";
                    else if (status === 401) message = "Unauthorized. Please log in.";
                    else if (status === 403) message = "Forbidden access.";
                    else if (status === 500) message = "Server error.";
                    NotificationHandlerGet.showError(message);
                }

                if (redirect.error) window.location.href = redirect.error;
            } else {
                NotificationHandlerGet.showError("Unexpected error: " + error.message);
            }
        }
    }
};
