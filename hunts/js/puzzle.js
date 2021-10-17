import $ from 'jquery'
import 'bootstrap/js/dist/collapse'
import { easeLinear, format, select } from 'd3'
import durationFilters from './human-duration'
import { Duration } from 'luxon'
import RobustWebSocket from 'robust-websocket'
import { encode } from 'html-entities'

import 'hunter2/js/base'
import 'hunter2/js/csrf.js'

import '../scss/puzzle.scss'
import { SocketHandler, setupNotifications} from './puzzleWebsocketHandlers'

/* global unlocks, hints */

function incorrect_answer(guess, timeout_length, timeout) {
  var milliseconds = Date.parse(timeout) - Date.now()
  var difference = timeout_length - milliseconds

  // There will be a small difference in when the server says we should re-enable the guessing and
  // when the client thinks we should due to latency. However, if the client and server clocks are
  // different it will be worse and could lead to a team getting disadvantaged or seeing tons of
  // errors. Hence in that case we use our own calculation and ignore latency.
  if (Math.abs(difference) > 1000) {
    milliseconds = timeout_length
  }
  doCooldown(milliseconds)
}

function correct_answer() {
  var form = $('#answer-form')
  if (form.length) {
    // We got a direct response before the WebSocket notified us (possibly because the WebSocket is broken
    // in this case, we still want to tell the user that they got the right answer. If the WebSocket is
    // working, this will be updated when it replies.
    form.after('<div id="correct-answer-message">Correct!</div>')
  }
}

function message(message, error) {
  var error_msg = $('<div class="submission-error-container"><p class="submission-error" title="' + error + '">' + message + '</p></div>')
  error_msg.appendTo($('#answer-form')).delay(5000).fadeOut(2000, function(){$(this).remove()})
}

function evaluateButtonDisabledState(button) {
  var onCooldown = button.data('cooldown')
  var emptyAnswer = button.data('empty-answer')
  if (onCooldown || emptyAnswer) {
    button.attr('disabled', true)
  } else {
    button.removeAttr('disabled')
  }
}

function doCooldown(milliseconds) {
  var btn = $('#answer-button')
  btn.data('cooldown', true)
  evaluateButtonDisabledState(btn)

  var button = select('#answer-button')
  var size = button.node().getBoundingClientRect().width
  var g = button.select('svg')
    .append('g')

  var path = g.append('path')
  path.attr('fill', '#33e')
    .attr('opacity', 0.9)

  var flashDuration = 150
  path.transition()
    .duration(milliseconds)
    .ease(easeLinear)
    .attrTween('d', function () { return drawSliceSquare(size) })

  setTimeout(function () {
    g.append('circle')
      .attr('cx', size / 2)
      .attr('cy', size / 2)
      .attr('r', 0)
      .attr('fill', 'white')
      .attr('opacity', 0.95)
      .attr('stroke-width', 6)
      .attr('stroke', 'white')
      .transition()
      .duration(flashDuration)
      .ease(easeLinear)
      .attr('r', size / 2 * Math.SQRT2)
      .attr('fill-opacity', 0.3)
      .attr('stroke-opacity', 0.2)
  }, milliseconds - flashDuration)

  var text = g.append('text')
    .attr('x', size / 2)
    .attr('y', size / 2)
    .attr('fill', 'white')
    .attr('text-anchor', 'middle')
    .attr('font-weight', 'bold')
    .attr('font-size', 22)
    .attr('dominant-baseline', 'middle')
    .style('filter', 'url(#drop-shadow)')

  text.transition()
    .duration(milliseconds)
    .ease(easeLinear)
    .tween('text', function () {
      var oldthis = this
      return function (t) {
        var time = milliseconds * (1-t) / 1000
        select(oldthis).text(time < 1 ? format('.1f')(time) : format('.0f')(time))
      }
    })

  setTimeout(function () {
    g.remove()
    btn.removeData('cooldown')
    evaluateButtonDisabledState(btn)
  }, milliseconds)
}

function drawSliceSquare(size) {
  return function(proportion) {
    var angle = (proportion * Math.PI * 2) - Math.PI / 2
    var x = Math.cos(angle) * size
    var y = Math.sin(angle) * size
    var pathString = 'M ' + size / 2 + ',0' +
            ' L ' + size / 2 + ',' + size / 2 +
            ' l ' + x + ',' + y
    var pathEnd = ' Z'
    if (proportion < 0.875) {
      pathEnd = ' L 0,0 Z' + pathEnd
    }
    if (proportion < 0.625) {
      pathEnd = ' L 0,' + size + pathEnd
    }
    if (proportion < 0.375) {
      pathEnd = ' L ' + size + ',' + size + pathEnd
    }
    if (proportion < 0.125) {
      pathEnd = ' L ' + size + ',0' + pathEnd
    }
    return pathString + pathEnd
  }
}

export function drawCooldownText(milliseconds) {
  return function(proportion) {
    var time = milliseconds * proportion / 1000
    select(this).text(time < 1 ? format('.1')(time) : format('1')(time))
  }
}

export function drawFlashSquare() {
  return function() {
    return ''
  }
}

function addSVG() {
  var button = select('#answer-button')
  if (button.empty()) {
    return
  }
  var svg = button.append('svg')
  var size = button.node().getBoundingClientRect().width
  svg.attr('width', size)
    .attr('height', size)

  var defs = svg.append('defs')

  var filter = defs.append('filter')
    .attr('id', 'drop-shadow')
    .attr('width', '200%')
    .attr('height', '200%')
  filter.append('feGaussianBlur')
    .attr('in', 'SourceAlpha')
    .attr('stdDeviation', 4)
    .attr('result', 'blur')
  filter.append('feOffset')
    .attr('in', 'blur')
    .attr('dx', 4)
    .attr('dy', 4)
    .attr('result', 'offsetBlur')
  var feMerge = filter.append('feMerge')
  feMerge.append('feMergeNode')
    .attr('in', 'offsetBlur')
  feMerge.append('feMergeNode')
    .attr('in', 'SourceGraphic')
}

var guesses = []

function addAnswer(user, guess, correct, guess_uid) {
  var guesses_table = $('#guesses .guess-viewer-header')
  guesses_table.after('<tr><td>' + encode(user) + '</td><td>' + encode(guess) + '</td></tr>')
  guesses.push(guess_uid)
}

function receivedNewAnswers(content) {
  content.forEach(info => {
    if (!guesses.includes(info.guess_uid)) {
      addAnswer(info.by, info.guess, info.correct, info.guess_uid)
    }
  })
}

function receivedOldAnswers(content) {
  content.forEach(info => {
    addAnswer(info.by, info.guess, info.correct, info.guess_uid)
  })
}

function receivedSolvedMsg(content) {
  let message = $('#correct-answer-message')
  const time = durationFilters.filters.durationForHumans(Duration.fromMillis(content.time * 1000).toISO())
  const html = `"${content.guess} by ${content.by} was correct! You spent ${time} on the puzzle. ` +
    `Taking you ${content.text}. <a class="puzzle-complete-redirect" href="${content.redirect}">go right now</a>`
  if (message.length) {
    // The server already replied so we already put up a temporary message; just update it
    message.html(html)
  } else {
    // That did not happen, so add the message
    var form = $('#answer-form')
    form.after(`<div id="correct-answer-message">${html}</div>`)
    form.remove()
  }
  setTimeout(function () {window.location.href = content.redirect}, 3000)
}

function updateUnlocks() {
  let entries = Array.from(unlocks.entries())
  entries.sort(function(a, b) {
    if (a[1].unlock < b[1].unlock) return -1
    else if (a[1].unlock > b[1].unlock) return 1
    return 0
  })
  let list = select('#unlocks')
    .selectAll('#unlocks > li')
    .data(entries)
  let listEnter = list.enter()
  let subList = listEnter.append('li')
    .merge(list)
    .html(function (d) {
      return d[1].guesses.join('<br>')
    })
    .append('ul')
    .attr('class', 'unlock-texts')
    .classed('new-clue', function(d) {return d[1].new})
    .each(function(d) {if (d[1].new) {intersectionObserver.observe(this)}})
  subList.append('li')
    .html(function(d) { return `<b>${d[1].unlock}</b>` })
  list.exit()
    .remove()

  subList.selectAll('ul.unlock-texts')
    .data(function(d) {
      let hintEntries = Object.entries(d[1].hints)
      hintEntries.sort(function(a, b) {
        if (a[1].unlock < b[1].unlock) return -1
        else if (a[1].unlock > b[1].unlock) return 1
        return 0
      })
      return hintEntries
    }).enter()
    .append('li')
    .attr('class', 'hint')
    .html(function (d) {
      return `${d[1].time}: <b>${d[1].hint}</b>`
    })
  entries.forEach((entry) => {
    entry[1].new = false
  })
}

function createBlankUnlock(uid) {
  unlocks.set(uid, {'unlock': null, 'guesses': [], 'hints': {}, 'new': true})
}

function receivedNewUnlock(content) {
  if (!(unlocks.has(content.unlock_uid))) {
    createBlankUnlock(content.unlock_uid)
  }
  let unlockInfo = unlocks.get(content.unlock_uid)
  unlockInfo.unlock = content.unlock
  var guess = encode(content.guess)
  if (!unlockInfo.guesses.includes(guess)) {
    unlockInfo.guesses.push(guess)
  }
  unlockInfo.new = true
  updateUnlocks()
}

function receivedChangeUnlock(content) {
  if (!(unlocks.has(content.unlock_uid))) {
    throw `WebSocket changed invalid unlock: ${content.unlock_uid}`
  }
  unlocks.get(content.unlock_uid).unlock = content.unlock
  updateUnlocks()
}

function receivedDeleteUnlock(content) {
  if (!(unlocks.has(content.unlock_uid))) {
    throw `WebSocket deleted invalid unlock: ${content.unlock_uid}`
  }
  unlocks.delete(content.unlock_uid)
  updateUnlocks()
}

function receivedDeleteUnlockGuess(content) {
  if (!(unlocks.has(content.unlock_uid))) {
    throw `WebSocket deleted guess for invalid unlock: ${content.unlock_uid}`
  }
  if (!(unlocks.get(content.unlock_uid).guesses.includes(content.guess))) {
    throw `WebSocket deleted invalid guess (can happen if team made identical guesses): ${content.guess}`
  }
  var unlockguesses = unlocks.get(content.unlock_uid).guesses
  var i = unlockguesses.indexOf(content.guess)
  unlockguesses.splice(i, 1)
  if (unlockguesses.length == 0) {
    unlocks.delete(content.unlock_uid)
  }
  updateUnlocks()
}

function updateHints() {
  var entries = Object.entries(hints)
  entries.sort(function (a, b) {
    if (a[1].time < b[1].time) return -1
    else if(a[1].time > b[1].time) return 1
    return 0
  })
  var list = select('#hints')
    .selectAll('li')
    .data(entries)
  list.enter()
    .append('li')
    .merge(list)
    .html(function (d) {
      return `${d[1].time}: <b>${d[1].hint}</b>`
    })
    .classed('new-clue', function(d) {return d[1].new})
    .each(function(d) {if (d[1].new) {intersectionObserver.observe(this)}})
  list.exit()
    .remove()
  entries.forEach((e) => {
    e[1].new = false
  })
}


function receivedNewHint(content) {
  if (content.depends_on_unlock_uid === null) {
    hints[content.hint_uid] = {'time': content.time, 'hint': content.hint, 'new': true}
    updateHints()
  } else {
    if (!(unlocks.has(content.depends_on_unlock_uid))) {
      createBlankUnlock(content.depends_on_unlock_uid)
    }
    unlocks.get(content.depends_on_unlock_uid).hints[content.hint_uid] = {'time': content.time, 'hint': content.hint}
    updateUnlocks()
  }
}

function receivedDeleteHint(content) {
  if (!(content.hint_uid in hints || (unlocks.has(content.depends_on_unlock_uid) &&
         content.hint_uid in unlocks.get(content.depends_on_unlock_uid).hints))) {
    throw `WebSocket deleted invalid hint: ${content.hint_uid}`
  }
  if (content.depends_on_unlock_uid === null) {
    delete hints[content.hint_uid]
    updateHints()
  } else {
    delete unlocks.get(content.depends_on_unlock_uid).hints[content.hint_uid]
    updateUnlocks()
  }
}

function receivedError(content) {
  throw content.error
}

function intersectionCallback(entries) {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('new-clue-fading')
      entry.target.addEventListener('animationend', (e) => {
        e.target.classList.remove('new-clue', 'new-clue-fading')
      })
      intersectionObserver.unobserve(entry.target)
    }
  })
}
const intersectionObserver = new IntersectionObserver(intersectionCallback)

var lastUpdated

function openEventSocket() {
  const socketHandlers = {
    'announcement': new SocketHandler(window.alertList.addAnnouncement, true, 'New announcement'),
    'delete_announcement': new SocketHandler(window.alertList.deleteAnnouncement),
    'new_guesses': new SocketHandler(receivedNewAnswers),
    'old_guesses': new SocketHandler(receivedOldAnswers),
    'solved': new SocketHandler(receivedSolvedMsg, true, 'Puzzle solved'),
    'new_unlock': new SocketHandler(receivedNewUnlock, true, 'New unlock'),
    'old_unlock': new SocketHandler(receivedNewUnlock),
    'change_unlock': new SocketHandler(receivedChangeUnlock, true, 'Updated unlock'),
    'delete_unlock': new SocketHandler(receivedDeleteUnlock),
    'delete_unlockguess': new SocketHandler(receivedDeleteUnlockGuess),
    'new_hint': new SocketHandler(receivedNewHint, true, 'New hint'),
    'old_hint': new SocketHandler(receivedNewHint),
    'delete_hint': new SocketHandler(receivedDeleteHint),
    'error': new SocketHandler(receivedError),
  }

  var ws_scheme = (window.location.protocol == 'https:' ? 'wss' : 'ws') + '://'
  var sock = new RobustWebSocket(
    ws_scheme + window.location.host + '/ws' + window.location.pathname, undefined,
    {
      timeout: 30000,
      shouldReconnect: function(event, ws) {
        if (event.code === 1008 || event.code === 1011) return
        // reconnect with exponential back-off and 10% jitter until 7 attempts (32 second intervals thereafter)
        return (ws.attempts < 7 ? Math.pow(2, ws.attempts) * 500 : 32000) * (1 + Math.random() * 0.1)
      },
    },
  )
  sock.onmessage = function(e) {
    var data = JSON.parse(e.data)
    lastUpdated = Date.now()

    if (!(data.type in socketHandlers)) {
      throw `Invalid message type: ${data.type}, content: ${data.content}`
    } else {
      var handler = socketHandlers[data.type]
      if (typeof handler === 'function') {
        handler(data.content)
      } else {
        handler.handle(data.content)
      }
    }
  }
  sock.onerror = function() {
    let conn_status = $('#connection-status')
    conn_status.html('<p class="connection-error">' +
      'Websocket is disconnected; attempting to reconnect. ' +
      'If the problem persists, please notify the admins.</p>',
    )
  }
  sock.onopen = function() {
    let error = $('#connection-status > .connection-error')
    // If connecting when there is an existing error message, hide it and display a
    // message to say we reconnected.
    if (error.length) {
      error.remove()
      let conn_status = $('#connection-status')
      let msg = $('<p class="connection-opened">' +
        'Websocket connection re-established.</p>',
      )
      msg.appendTo(conn_status).delay(5000).fadeOut(2000, function() {
        $(this).remove()
      })
    }
    if (lastUpdated != undefined) {
      sock.send(JSON.stringify({'type': 'guesses-plz', 'from': lastUpdated}))
      sock.send(JSON.stringify({'type': 'hints-plz', 'from': lastUpdated}))
      sock.send(JSON.stringify({'type': 'unlocks-plz'}))
    } else {
      sock.send(JSON.stringify({'type': 'guesses-plz', 'from': 'all'}))
    }
  }
}

$(function() {
  addSVG()
  updateHints()
  updateUnlocks()

  let field = $('#answer-entry')
  let button = $('#answer-button')

  function fieldKeyup() {
    if (!field.val()) {
      button.data('empty-answer', true)
    } else {
      button.removeData('empty-answer')
    }
    evaluateButtonDisabledState(button)
  }
  field.on('input', fieldKeyup)

  setupNotifications()
  openEventSocket()

  $('#answer-form').submit(function(e) {
    e.preventDefault()
    if (!field.val()) {
      field.focus()
      return
    }

    var data = {
      answer: field.val(),
    }
    $.ajax({
      type: 'POST',
      url: 'an',
      data: $.param(data),
      contentType: 'application/x-www-form-urlencoded; charset=UTF-8',
      success: function(data) {
        field.val('')
        fieldKeyup()
        if (data.correct == 'true') {
          correct_answer()
        } else {
          incorrect_answer(data.guess, data.timeout_length, data.timeout_end, data.unlocks)
        }
      },
      error: function(xhr, status, error) {
        button.removeData('cooldown')
        if (xhr.responseJSON && xhr.responseJSON.error == 'too fast') {
          message('Slow down there, sparky! You\'re supposed to wait 5s between submissions.', '')
        } else if (xhr.responseJSON && xhr.responseJSON.error == 'already answered') {
          message('Your team has already correctly answered this puzzle!', '')
        } else {
          message('There was an error submitting the answer.', error)
        }
      },
      dataType: 'json',
    })
  })

  var soln_content = $('#soln-content')
  var soln_button = $('#soln-button')

  if (soln_content.length && soln_button.length) {
    soln_content.on('show.bs.collapse', function() {
      var url = soln_button.data('url')
      soln_content.load(url)
      $(this).unbind('show.bs.collapse')
    })
    soln_content.on('shown.bs.collapse', function() {
      soln_button.text('Hide Solution')
    })
    soln_content.on('hidden.bs.collapse', function() {
      soln_button.text('Show Solution')
    })
  }
})
