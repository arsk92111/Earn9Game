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
            error: "/account/page/login/",
        },
        onSuccess: (data) => {
            const player = data?.data;
            console.log("Player data:", player);   
            const coinsEl = document.getElementById("coins");
            const profileNameEl = document.getElementById("profile-name");

            if (profileNameEl && player?.user) {
                const { db_fullname, db_phone_number, email } = player.user;

                const displayName = db_fullname?.trim() || db_phone_number?.trim() || email || "No Name";
                profileNameEl.innerText = displayName;
            }

            if (player && typeof player.coins === "number" && coinsEl) {
                coinsEl.innerText = `${player.coins} Coins`;
            } else if (coinsEl) {
                coinsEl.innerText = "0 Coins";
            }

            if (loader) loader.style.display = "none";
        },
        onError: (status, errors) => {
            console.error("Fetch error:", errors);
            const message = errors?.errors?.message || errors?.message;
            NotificationHandlerGet.showError(message); 
            if (loader) loader.style.display = "none";
        }
    });
}
