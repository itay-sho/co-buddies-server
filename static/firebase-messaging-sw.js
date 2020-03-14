importScripts('https://www.gstatic.com/firebasejs/7.10.0/firebase-app.js');
importScripts('https://www.gstatic.com/firebasejs/7.10.0/firebase-messaging.js');

const firebaseConfig = {
    apiKey: "AIzaSyCkWIV6dQbYlUa-jU07FZfXGJKC8Kpeb7Q",
    authDomain: "co-buddies.firebaseapp.com",
    databaseURL: "https://co-buddies.firebaseio.com",
    projectId: "co-buddies",
    storageBucket: "co-buddies.appspot.com",
    messagingSenderId: "988924831308",
    appId: "1:988924831308:web:e46ac712f53892b40ab6e9"
};
// Initialize Firebase
firebase.initializeApp(firebaseConfig);
const messaging = firebase.messaging();

messaging.setBackgroundMessageHandler((payload) => {
    // Customize notification here
    const notificationTitle = payload.data.title;
    const notificationOptions = {
        body: payload.data.body,
        tag: 'cobuddies-newmessage-notification',
        renotify: true
    };

    return self.registration.showNotification(notificationTitle, notificationOptions);
});