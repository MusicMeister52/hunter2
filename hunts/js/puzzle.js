/*
 * Copyright (C) 2021 The Hunter2 Contributors.
 *
 * This file is part of Hunter2.
 *
 * Hunter2 is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free
 * Software Foundation, either version 3 of the License, or (at your option) any later version.
 *
 * Hunter2 is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
 * PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License along with Hunter2.  If not, see <http://www.gnu.org/licenses/>.
 */

import $ from 'jquery'
import 'bootstrap/js/dist/button'
import 'bootstrap/js/dist/collapse'
import {easeLinear, format, select} from 'd3'
import durationFilters from './human-duration'
import {Duration} from 'luxon'
import RobustWebSocket from 'robust-websocket'
import {encode} from 'html-entities'
import Vue from 'vue'

import 'hunter2/js/base'
import 'hunter2/js/csrf.js'

import '../scss/puzzle.scss'
import ClueList from './clue-list.vue'
import {setupNotifications, SocketHandler} from './puzzleWebsocketHandlers'

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
  let onCooldown = button.dataset.cooldown
  let emptyAnswer = button.dataset.emptyAnswer
  button.disabled = onCooldown || emptyAnswer
}

function doCooldown(milliseconds) {
  let btn = document.getElementById('answer-button')
  btn.dataset.cooldown = true
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
  window.puzzle_solved = true
  let message = $('#correct-answer-message')
  const time = durationFilters.filters.durationForHumans(Duration.fromMillis(content.time * 1000).toISO())
  const html = `"${content.guess}" by ${content.by} was correct! You spent ${time} on the puzzle. ` +
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

function receivedError(content) {
  throw content.error
}

var lastUpdated

function openEventSocket() {
  const socketHandlers = {
    'announcement': new SocketHandler(window.alertList.addAnnouncement, true, 'New announcement'),
    'delete_announcement': new SocketHandler(window.alertList.deleteAnnouncement),
    'new_guesses': new SocketHandler(receivedNewAnswers),
    'old_guesses': new SocketHandler(receivedOldAnswers),
    'solved': new SocketHandler(receivedSolvedMsg, true, 'Puzzle solved'),
    'new_unlock': new SocketHandler(window.clueList.newUnlock, true, 'New unlock'),
    'old_unlock': new SocketHandler(window.clueList.newUnlock),
    'change_unlock': new SocketHandler(window.clueList.changeUnlock, true, 'Updated unlock'),
    'delete_unlock': new SocketHandler(window.clueList.deleteUnlock),
    'delete_unlockguess': new SocketHandler(window.clueList.deleteUnlockGuess),
    'new_hint': new SocketHandler(window.clueList.newHint, true, 'New hint'),
    'old_hint': new SocketHandler(window.clueList.newHint),
    'delete_hint': new SocketHandler(window.clueList.deleteHint),
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

window.addEventListener('DOMContentLoaded', function() {
  addSVG()

  window.clueList = new Vue({
    ...ClueList,
    data: {
      hints: window.hints,
      unlocks: window.unlocks,
      hintRev: 1,
      unlockRev: 1,
    },
    el: '#clue-list',
  })

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

  const solution_button = document.getElementById('solution-button')
  const solution_content = document.getElementById('solution-content')

  if (solution_button != null && solution_content != null) {
    solution_content.addEventListener('show.bs.collapse', function populateSolution(event) {
      const url = solution_button.dataset.url
      fetch(url).then(response => response.text()).then(text => { solution_content.innerHTML = text })
      event.target.removeEventListener('show.bs.collapse', populateSolution)
    })
    solution_content.addEventListener('shown.bs.collapse', function() {
      solution_button.text = 'Hide Solution'
    })
    solution_content.addEventListener('hidden.bs.collapse', function() {
      solution_button.text = 'Show Solution'
    })
  }
})
