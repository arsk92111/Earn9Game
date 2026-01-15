
async function submitLoginForm() {
    const email_or_phone = document.getElementsByName("email_or_phone")[0]?.value?.trim(); 
    const password = document.getElementsByName("password")[0]?.value?.trim();


    if (!email_or_phone || !password) {
        NotificationHandler.showError("Both email/phone and password are required.");
        return;
    }

    const isEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email_or_phone);
    const isPhone = /^\+?\d{7,15}$/.test(email_or_phone.replace(/\s|[-]/g, "")); // digit-based phone check

    let cleanData = {
        password: password
    };

    if (isEmail) {
        cleanData.email = email_or_phone;
    } else if (isPhone) {
        const hasCountryCode = /^\+/.test(email_or_phone);
        if (!hasCountryCode) {
            NotificationHandler.showError("Phone number must include country code, e.g., +92XXXXXXXXX");
            return;
        }

        cleanData.db_phone_number = email_or_phone;
    } else {
        NotificationHandler.showError("Invalid email or phone number format.");
        return;
    }

    ApiClient.post({
        url: "/api/login/",
        data: cleanData,
        isForm: false, // <== IMPORTANT! because we're sending JSON not FormData
        token: null,
        redirect: {
            success: "/Earn/page/home/",
            error: null
        },
        onSuccess: (data) => {
            NotificationHandler.showSuccess(data?.message || data?.data.message);
            localStorage.setItem("auth_token", data?.data.auth_token);
            localStorage.setItem("access_token", data?.data.access_token);
            localStorage.setItem("refresh_token", data?.data.refresh_token);
        },
        onError: (status, errors) => { 
            const message = errors?.errors?.message || errors?.message;
            if (status === 403) {
                localStorage.setItem("auth_token", errors?.errors?.auth_token);
                NotificationHandler.showError(message);
                window.location.href = `/page/verify_account/`;
            } else {
                NotificationHandler.showError(message);
            } 
        }
    });
}

async function submitLogoutForm() {
    const refreshToken = localStorage.getItem('refresh_token');

    if (!refreshToken) {
        NotificationHandler.showError("No active session found");
        window.location.href = "/";  // Force redirect
        return;
    } 

    ApiClient.post({
        url: "/api/logout/",
        data: {
            refresh_token: refreshToken  // Send refresh token
        },
        isForm: false,
        token: localStorage.getItem('access_token'),  // Send access token in header
        redirect: {
            success: "/",
            error: "/",
        },
        onSuccess: (data) => { 
            localStorage.removeItem("auth_token");
            localStorage.removeItem("access_token");
            localStorage.removeItem("refresh_token");

            NotificationHandler.showSuccess("Successfully logged out");
            window.location.href = "/";  // Force redirect
        },
        onError: (status, errors) => { 
            localStorage.clear();
            NotificationHandler.showError("Session expired. Please login again.");
            window.location.href = "/";
        }
    });
}
 

async function submitRegisterForm() {
    // const email = document.getElementsByName("email")[0]?.value?.trim(); 
    //  const isEmailMode = document.querySelector('.email-group').style.display !== 'none';
    const db_fullname = document.getElementsByName("db_fullname")[0]?.value?.trim();
    const countryCode = document.getElementsByName("country_code")[0]?.value?.trim();
    const db_phone_number = document.getElementsByName("db_phone_number")[0]?.value?.trim();
    const password = document.getElementsByName("password")[0]?.value?.trim();
 
    if (!countryCode || !db_phone_number) {
        NotificationHandler.showError("Both Country Code, Phone Number are required.");
        return;
    }

    // if (isEmailMode) {
    //     if (!email) {
    //         NotificationHandler.showError("Email are required.");
    //         return;
    //     }
    // }
    // else {
    //     if (!countryCode || !db_phone_number) {
    //         NotificationHandler.showError("Both Country Code, Phone Number are required.");
    //         return;
    //     } 
    // }

    // const cleanData = email
    //     ? { email: email, password: password, db_fullname: db_fullname }
    //     : { country_code: countryCode, db_phone_number: db_phone_number, password: password, db_fullname: db_fullname };

    if (!password) {
        NotificationHandler.showError("Password are required.");
        return;
    }
 
    const countryMap = {
        "+92": "Pakistan",
        "+91": "India",
        "+1": "USA",
        "+86": "China",
        "+880": "Bangladesh",
        "+81": "Japan",
        "+971": "UAE",
        "+44": "UK"
    };

    const db_country_address = countryMap[countryCode] || "Unknown";
    const cleanData = { country_code: countryCode, db_phone_number: db_phone_number, password: password, db_fullname: db_fullname, db_country_address: db_country_address };
 
    ApiClient.post({
        url: "/api/register/",
        data: cleanData,
        isForm: false,  
        token: null,
        redirect: {
            success: "/page/verify_account/",
            error: null
        },
        onSuccess: (data) => {
            NotificationHandler.showSuccess(data?.message || data?.data.message);
            localStorage.setItem("auth_token", data?.data.auth_token);
        },
        onError: (status, errors) => { 
            NotificationHandler.showError(errors?.errors?.message || errors?.message);
        }
    });
}

async function submitVerifyForm() { 
    const pin_code = document.getElementsByName("pin_code")[0]?.value?.trim(); 
    const cleanData = { pin_code: pin_code } 

    ApiClient.post({
        url: `/api/verify_account/${localStorage.getItem('auth_token')}/`,
        data: cleanData,
        isForm: false, 
        token: null,
        redirect: {
            success: "/",
            error: null
        },
        onSuccess: (data) => {
            NotificationHandler.showSuccess(data?.message || data?.data.message);
            localStorage.setItem("auth_token", data?.data.auth_token);
        },
        onError: (status, errors) => { 
            NotificationHandler.showError(errors?.errors?.message || errors?.message);
        }
    });
}


async function submitRegenerateForm() { 
    const cleanData = { }

    ApiClient.post({
        url: `/api/regenerate_code/${localStorage.getItem('auth_token')}/`,
        data: cleanData,
        isForm: false, 
        token: null,
        redirect: {
            success: null,
            error: null
        },
        onSuccess: (data) => {
            NotificationHandler.showSuccess(data?.message || data?.data.message);
            localStorage.setItem("auth_token", data?.data.auth_token);
        },
        onError: (status, errors) => {
            console.error("Register error:", errors);
            NotificationHandler.showError(errors?.errors?.message || errors?.message);
        }
    });
}


async function submitPasswordChangeForm() {
    const oldPassword = document.getElementsByName("oldPassword")[0]?.value?.trim();
    const newPassword1 = document.getElementsByName("newPassword1")[0]?.value?.trim();
    const newPassword2 = document.getElementsByName("newPassword2")[0]?.value?.trim(); 

    const cleanData = { oldPassword: oldPassword, newPassword1: newPassword1, newPassword2: newPassword2 }

    ApiClient.post({
        url: `/api/changePassword/${localStorage.getItem('auth_token')}/`,
        data: cleanData,
        isForm: false,
        token: localStorage.getItem('access_token'),
        redirect: {
            success: null,
            error: null
        },
        onSuccess: (data) => {
            NotificationHandler.showSuccess(data?.message || data?.data.message);
            localStorage.setItem("auth_token", data?.data.auth_token);
        },
        onError: (status, errors) => {
            console.error("Register error:", errors);
            NotificationHandler.showError(errors?.errors?.message || errors?.message);
        }
    });
}



async function submitProfileChangeForm() {
    const db_fullname = document.getElementsByName("db_fullname")[0]?.value?.trim(); 

    const cleanData = { db_fullname: db_fullname }

    ApiClient.put({
        url: `/api/changeProfile/`,
        data: cleanData,
        isForm: false,
        token: localStorage.getItem('access_token'),
        redirect: {
            success: null,
            error: null
        },
        onSuccess: (data) => {
            NotificationHandler.showSuccess(data?.message || data?.data.message);
            localStorage.setItem("auth_token", data?.data.auth_token);
        },
        onError: (status, errors) => {
            console.error("Register error:", errors);
            NotificationHandler.showError(errors?.errors?.message || errors?.message);
        }
    });
}

