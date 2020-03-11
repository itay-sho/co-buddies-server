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
    console.log('[firebase-messaging-sw.js] Received background message ', payload);
    // Customize notification here
    const notificationTitle = payload.data.title;
    const notificationOptions = {
        body: payload.data.body,
        tag: 'cobuddies-newmessage-notification',
        renotify: true
    };

    return self.registration.showNotification(notificationTitle, notificationOptions);
});

self.addEventListener('notificationclick', function(event) {
    const clickedNotification = event.notification;
    clickedNotification.close();

    // This looks to see if the current is already open and
    // focuses if it is
    event.waitUntil(self.clients.matchAll({includeUncontrolled: true, type: 'window'}).then((clientList) => {
        console.log(clientList);
        for (let i = 0; i < clientList.length; i++) {
            const client = clientList[i];
            if (client.url === event.notification.url && 'focus' in client)
                return client.focus();
            else
                console.log('client url: ', client.url);
        }
    }));
});