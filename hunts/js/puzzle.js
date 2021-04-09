import $ from 'jquery'
import 'bootstrap/js/dist/collapse'
import { easeLinear, format, select } from 'd3'
import RobustWebSocket from 'robust-websocket'
import { encode } from 'html-entities'

import 'hunter2/js/base'
import 'hunter2/js/csrf.js'

import '../scss/puzzle.scss'

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
  var form = $('.form-inline')
  if (form.length) {
    // We got a direct response before the WebSocket notified us (possibly because the WebSocket is broken
    // in this case, we still want to tell the user that they got the right answer. If the WebSocket is
    // working, this will be updated when it replies.
    form.after('<div id="correct-answer-message">Correct!</div>')
  }
}

function message(message, error) {
  var error_msg = $('<div class="submission-error-container"><p class="submission-error" title="' + error + '">' + message + '</p></div>')
  error_msg.appendTo($('.form-inline')).delay(5000).fadeOut(2000, function(){$(this).remove()})
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

  /*var filter = defs.append("filter")
		.attr("id", "drop-shadow")
		.attr("x", "0")
		.attr("y", "0")
		.attr(*/
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
      if (info.correct) {
        var message = $('#correct-answer-message')
        var html = `"${info.guess} was correct! Taking you ${info.text}. <a class="puzzle-complete-redirect" href="${info.redirect}">go right now</a>`
        if (message.length) {
          // The server already replied so we already put up a temporary message; just update it
          message.html(html)
        } else {
          // That did not happen, so add the message
          var form = $('.form-inline')
          form.after(`<div id="correct-answer-message">${html}</div>`)
          form.remove()
        }
        setTimeout(function () {window.location.href = info.redirect}, 3000)
      }
    }
  })
}

function receivedOldAnswers(content) {
  content.forEach(info => {
    addAnswer(info.by, info.guess, info.correct, info.guess_uid)
  })
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
}

function createBlankUnlock(uid) {
  unlocks.set(uid, {'unlock': null, 'guesses': [], 'hints': {}})
}

function receivedNewUnlock(content) {
  if (!(content.unlock_uid in unlocks)) {
    createBlankUnlock(content.unlock_uid)
  }
  unlocks.get(content.unlock_uid).unlock = content.unlock
  var guess = encode(content.guess)
  if (!unlocks.get(content.unlock_uid).guesses.includes(guess)) {
    unlocks.get(content.unlock_uid).guesses.push(guess)
  }
  updateUnlocks()
}

function receivedChangeUnlock(content) {
  if (!(content.unlock_uid in unlocks)) {
    throw `WebSocket changed invalid unlock: ${content.unlock_uid}`
  }
  unlocks.get(content.unlock_uid).unlock = content.unlock
  updateUnlocks()
}

function receivedDeleteUnlock(content) {
  if (!(content.unlock_uid in unlocks)) {
    throw `WebSocket deleted invalid unlock: ${content.unlock_uid}`
  }
  delete unlocks[content.unlock_uid]
  updateUnlocks()
}

function receivedDeleteUnlockGuess(content) {
  if (!(content.unlock_uid in unlocks)) {
    throw `WebSocket deleted guess for invalid unlock: ${content.unlock_uid}`
  }
  if (!(unlocks.get(content.unlock_uid).guesses.includes(content.guess))) {
    throw `WebSocket deleted invalid guess (can happen if team made identical guesses): ${content.guess}`
  }
  var unlockguesses = unlocks.get(content.unlock_uid).guesses
  var i = unlockguesses.indexOf(content.guess)
  unlockguesses.splice(i, 1)
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
  list.exit()
    .remove()
}


function receivedNewHint(content) {
  if (content.depends_on_unlock_uid === null) {
    hints[content.hint_uid] = {'time': content.time, 'hint': content.hint}
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

var lastUpdated

function openEventSocket() {
  const socketHandlers = {
    'announcement': window.alertList.addAnnouncement,
    'delete_announcement': window.alertList.deleteAnnouncement,
    'new_guesses': receivedNewAnswers,
    'old_guesses': receivedOldAnswers,
    'new_unlock': receivedNewUnlock,
    'old_unlock': receivedNewUnlock,
    'change_unlock': receivedChangeUnlock,
    'delete_unlock': receivedDeleteUnlock,
    'delete_unlockguess': receivedDeleteUnlockGuess,
    'new_hint': receivedNewHint,
    'old_hint': receivedNewHint,
    'delete_hint': receivedDeleteHint,
    'error': receivedError,
  }

  var ws_scheme = (window.location.protocol == 'https:' ? 'wss' : 'ws') + '://'
  var sock = new RobustWebSocket(ws_scheme + window.location.host + '/ws' + window.location.pathname)
  sock.onmessage = function(e) {
    var data = JSON.parse(e.data)
    lastUpdated = Date.now()

    if (!(data.type in socketHandlers)) {
      throw `Invalid message type: ${data.type}, content: ${data.content}`
    } else {
      var handler = socketHandlers[data.type]
      handler(data.content)
    }
  }
  sock.onerror = function() {
    //TODO this message is ugly and disappears after a while
    message('Websocket is broken. You will not receive new information without refreshing the page.')
  }
  sock.onopen = function() {
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

  openEventSocket()

  $('.form-inline').submit(function(e) {
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
