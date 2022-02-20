import Popover from 'bootstrap/js/dist/popover'
import 'bootstrap/js/dist/tooltip'

export function SocketHandler(handler, notify=false, notificationText='') {
  this.handler = handler
  this.notify = notify
  this.notificationText = notificationText
}

SocketHandler.prototype.handle = function(data) {
  this.handler(data)
  if (this.notify) {
    if (window.localStorage.getItem('notificationSounds') === 'true') {
      document.getElementById('notification-sound').play().catch(() => {
        window.alertList.addAnnouncement({
          announcement_id: '_autoplay_rejected',
          message: 'Playing notification sound failed. You may wish to enable autoplay audio.',
          variant: 'warning',
          dismissible: true,
        })
      })
    }
    if ('Notification' in window && window.Notification.permission === 'granted' && window.localStorage.getItem('notificationNative') === 'true') {
      this.makeNotification(data)
    }
  }
}

SocketHandler.prototype.makeNotification = function(data) {
  if (!document.hasFocus()) {
    let name = document.getElementById('puzzle-title').textContent
    let options = {
      'icon': icon,
      'body': typeof this.notificationText === 'function' ? this.notificationText(data) : this.notificationText,
    }
    new Notification(name, options)
  }
}

function getLargestFavicon () {
  function getSize (el) {
    // Assume that all icons have only one size (true at the time of writing)
    if (el.sizes[0] === 'any') return Infinity
    return (el.sizes[0] && parseInt(el.sizes[0], 10)) || 0
  }
  const icons = [...document.querySelectorAll('link[rel="icon"]')]
  return icons.length > 0 ? icons.reduce((a, b) => {
    return getSize(a) > getSize(b) ? a : b
  }).href : null
}
const icon = getLargestFavicon()

export function setupNotifications() {

  if (window.localStorage.getItem('notificationSounds') === null) {
    window.localStorage.setItem('notificationSounds', 'false')
  }
  if (window.localStorage.getItem('notificationNative') === null) {
    window.localStorage.setItem('notificationNative', 'false')
  }

  const notificationButton = document.getElementById('notification-button')
  const notificationContainer = document.getElementById('notification-popover-container')
  const notificationContent = document.getElementById(notificationButton.dataset.contentId)
  const notificationPopover = new Popover(notificationButton, {
    content: notificationContent.innerHTML,
    sanitize: false,
  })
  notificationContent.remove()

  notificationButton.addEventListener('inserted.bs.popover', () => {
    const browserNotificationsCheckbox = document.getElementById('browser-notifications-cb')
    browserNotificationsCheckbox.checked = (window.localStorage.getItem('notificationNative') === 'true')
    browserNotificationsCheckbox.addEventListener('change', function(event) {
      let checkbox = event.target
      let enable = checkbox.checked
      window.localStorage.setItem('notificationNative', enable.toString())
      setNotificationIndicators()
      if (enable) {
        if (window.Notification.permission === 'default') {
          window.Notification.requestPermission().then(() => {
            setNotificationIndicators()
          })
        }
      }
    })
    const soundNotificationsCheckbox = document.getElementById('sound-notifications-cb')
    soundNotificationsCheckbox.checked = (window.localStorage.getItem('notificationSounds') === 'true')
    soundNotificationsCheckbox.addEventListener('change', function(event) {
      let checkbox = event.target
      let enable = checkbox.checked
      window.localStorage.setItem('notificationSounds', enable.toString())
      setNotificationIndicators()
    })
    document.getElementById('notification-permission-msg').style.visibility = (
      window.localStorage.getItem('notificationNative') === 'true' && window.Notification.permission !== 'granted' ? 'visible' : 'hidden'
    )
    document.getElementById('sound-permission-msg').style.visibility = (
      window.localStorage.getItem('notificationSounds') === 'true' ? 'visible' : 'hidden'
    )
  })

  document.body.addEventListener('click', function(event) {
    if (!notificationButton.contains(event.target) && !notificationContainer.contains(event.target)) {
      notificationPopover.hide()
    }
  })

  function setNotificationIndicators() {
    let willDoSounds = window.localStorage.getItem('notificationSounds') === 'true'
    let willDoNativeNotifications = (
      window.localStorage.getItem('notificationNative') === 'true' &&
      window.Notification.permission === 'granted'
    )
    if (willDoSounds || willDoNativeNotifications) {
      notificationButton.textContent = '🔔'
    } else {
      notificationButton.textContent = '🔕'
    }
  }
  setNotificationIndicators()
}

