import $ from 'jquery'
import 'bootstrap/js/dist/popover'
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
      $('#notification-sound')[0].play().catch(() => {
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
    let name = $('h1').text()
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
  return [...document.querySelectorAll('link[rel="icon"]')].reduce((a, b) => {
    return getSize(a) > getSize(b) ? a : b
  }).href
}
const icon = getLargestFavicon()

export function setupNotifications() {

  if (window.localStorage.getItem('notificationSounds') === null) {
    window.localStorage.setItem('notificationSounds', 'false')
  }
  if (window.localStorage.getItem('notificationNative') === null) {
    window.localStorage.setItem('notificationNative', 'false')
  }

  let notificationButton = $('#notification-button')
  function setNotificationIndicators() {
    let willDoSounds = window.localStorage.getItem('notificationSounds') === 'true'
    let willDoNativeNotifications = (
      window.localStorage.getItem('notificationNative') === 'true' &&
      window.Notification.permission === 'granted'
    )
    if (willDoSounds || willDoNativeNotifications) {
      notificationButton.text('🔔')
    } else {
      notificationButton.text('🔕')
    }
    $('#notification-permission-msg').toggle(
      window.localStorage.getItem('notificationNative') === 'true' && window.Notification.permission !== 'granted',
    )
    $('#sound-permission-msg').toggle(willDoSounds)
  }
  setNotificationIndicators()
  notificationButton.popover({
    content: $('#notification-popover').html(),
    html: true,
    sanitize: false,
    placement: 'bottom',
    trigger: 'click',
    boundary: document.getElementsByTagName('main')[0],
  }).on('inserted.bs.popover', () => {
    $('#browser-notifications-cb').prop('checked', window.localStorage.getItem('notificationNative') === 'true')
    $('#sound-notifications-cb').prop('checked', window.localStorage.getItem('notificationSounds') === 'true')
  })
  // Remove the original HTML so as not to duplicate IDs
  $('#notification-popover').remove()
  // Hide popover on clicking outside the button or popover. 'focus' trigger would also hide when focusing
  // anything inside the popover.
  $('html').on('click', function(e) {
    let target = e.target
    if (!notificationButton.is(target) && notificationButton.has(target).length === 0 && $('.popover').has(target).length === 0) {
      notificationButton.popover('hide')
    }
  })
  $('body').on('change', '#browser-notifications-cb', function() {
    let checkbox = $(this)
    let enable = checkbox.is(':checked')
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
  $('body').on('change', '#sound-notifications-cb', function() {
    let checkbox = $(this)
    let enable = checkbox.is(':checked')
    window.localStorage.setItem('notificationSounds', enable.toString())
    setNotificationIndicators()
  })
}

