async function fetchAuthenticatedPlayerData() {
    const token = localStorage.getItem("access_token");

    if (!token) {
        NotificationHandlerGet.showError("No token found. Please log in.");
        return;
    } 
    const loader = document.getElementById("loader");
    if (loader) loader.style.display = "block";

    ApiClientGet.get({
        url: "/Earn/api/my_profile/",
        token: token,
        redirect: {
            error: "/",
        },
        onSuccess: (data) => {
            const player = data?.data;  
            const coinsEl = document.getElementById("coins");
            const profileNameEl = document.getElementById("profile-name");

            if (profileNameEl && player?.user) {
                const { db_fullname, db_phone_number, email , db_photo } = player.user;

                const displayName = db_fullname?.trim() || db_phone_number?.trim() || email || "No Name";
                profileNameEl.innerText = displayName;
                document.querySelector(".profile-img").src = `https://i.pravatar.cc/150?img=${db_photo}`;
            }

            if (player && typeof player.coins === "number" && coinsEl) {
                coinsEl.innerText = `${player.coins} Coins`;
            } else if (coinsEl) {
                coinsEl.innerText = "0 Coins";
            }

            if (loader) loader.style.display = "none";
        },
        onError: (status, errors) => { 
            const message = errors?.errors?.message || errors?.message;
            NotificationHandlerGet.showError(message); 
            if (loader) loader.style.display = "none";
        }
    });
}


async function fetchLeaderBoard() {
    const token = localStorage.getItem("access_token");

    if (!token) {
        NotificationHandlerGet.showError("No token found. Please log in.");
        return;
    }
    const loader = document.getElementById("loader");
    if (loader) loader.style.display = "block";

    ApiClientGet.get({
        url: "/Earn/api/leaderboard/",
        token: token,
        redirect: {
            error: "/",
        },
        onSuccess: (data) => {
            const player = data?.data;
            // console.log("Player data:", player);
            const LeaderEl = document.getElementById("leaderboard"); 
            if (LeaderEl) {
                player.map(p => {
                    const LeaderItem = document.createElement('div');
                    LeaderItem.classList.add("leaderboard-item");
                    LeaderItem.innerHTML = `
                        <span>🥇 ${p.user.db_fullname} </span>
                        <span>${p.coins} Coins</span>
                    `;
                    LeaderEl.appendChild(LeaderItem);
                });

            }
            
            if (loader) loader.style.display = "none";
        },
        onError: (status, errors) => { 
            const message = errors?.errors?.message || errors?.message;
            NotificationHandlerGet.showError(message);
            if (loader) loader.style.display = "none";
        }
    });
}

async function fetchProfileData() {
    const token = localStorage.getItem("access_token");

    if (!token) {
        NotificationHandlerGet.showError("No token found. Please log in.");
        return;
    }
    const loader = document.getElementById("loader");
    if (loader) loader.style.display = "block";

    ApiClientGet.get({
        url: "/Earn/api/my_profile/",
        token: token,
        redirect: {
            error: "/",
        },
        onSuccess: (data) => {
            const player = data?.data;
            const coinsEl = document.getElementById("coins");
            const balanceE2 = document.getElementById("balance");
            const profileNameEl = document.getElementById("profile-fullname-header");
            const profileNameE2 = document.getElementById("profile-fullname");
            const profileNameE3 = document.getElementById("db_fullname");

            const profilePhoneE1 = document.getElementById("profile-phoneNumber");
            const profileCountryE1 = document.getElementById("profile-country");
            const profileAuthE1 = document.getElementById("profile-auth_token");

            if (profileNameEl && profileNameE2 && profilePhoneE1 && profileCountryE1 && profileAuthE1 && player?.user) {
                const { db_fullname, db_phone_number, email, db_photo, db_country_address, auth_token } = player.user;

                const displayName = db_fullname?.trim() || db_phone_number?.trim() || email || "No Name";
                profileNameEl.innerText = displayName;
                profileNameE2.innerText = displayName;
                profileNameE3.value = displayName;
                profilePhoneE1.innerText = db_phone_number?.trim() || "+92-312-1234567";
                profileCountryE1.innerText = db_country_address?.trim() || "Unknown";
                profileAuthE1.innerText = auth_token?.trim();
                document.querySelector(".profile-photo").src = `https://i.pravatar.cc/150?img=${db_photo}`;
            }

            if (player && typeof player.coins === "number" && coinsEl && balanceE2) {
                coinsEl.innerText = `${player.coins} Coins`;
                balanceE2.innerHTML = `${player.coins} Coins`;
            } else if (coinsEl && balanceE2) {
                coinsEl.innerText = "0 Coins";
            }

            if (loader) loader.style.display = "none";
        },
        onError: (status, errors) => {
            const message = errors?.errors?.message || errors?.message;
            NotificationHandlerGet.showError(message);
            if (loader) loader.style.display = "none";
        }
    });
}
