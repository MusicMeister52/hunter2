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

import Cookies from 'js-cookie'

import {fadingMessage} from './puzzle'
import {SocketHandler} from './puzzleWebsocketHandlers'

export default {
  computed: {
    none() {
      return this.hints.size === 0 && this.unlocks.size === 0 ? 'None yet' : ''
    },
    sortedHints() {
      return this.hintArray(this.hints)
    },
    sortedUnlocks() {
      return Array.from(this.unlocks.entries(), u => [u[0], {
        unlock: u[1].unlock,
        guesses: u[1].guesses,
        isNew: u[1].isNew,
        hints: this.hintArray(u[1].hints),
      }])
    },
  },
  data: function() {
    return {
      lastUpdated: Date.now(),
    }
  },
  methods: {
    createBlankUnlock(uid) {
      this.unlocks.set(uid, {'unlock': null, 'guesses': new Set(), 'hints': new Map()})
    },
    hintArray(hintMap) {
      return Array.from(
        hintMap.entries(),
      ).sort(
        (a, b) => (a[1].time.localeCompare(b[1].time)),
      )
    },
    acceptHint(hintId, unlockId) {
      fetch(
        'accept_hint',
        {
          method: 'POST',
          body: new URLSearchParams({
            id: hintId.toString(),
          }),
          headers: {
            'X-CSRFToken': Cookies.get('csrftoken'),
          },
        },
      ).then(
        res => res.json(),
      ).then(
        data => {
          if ('error' in data) {
            console.log('Server returned error when trying to accept the hint.', data.error)
            fadingMessage(
              document.querySelector('#hints'),
              'Server returned error when trying to accept the hint.',
              data.error,
            )
            return
          }
          let hintData
          if (unlockId === null) {
            hintData = this.hints.get(hintId)
          } else {
            hintData = this.unlocks.get(unlockId).hints.get(hintId)
          }
          // if the response arrives before the websocket message, display a holding message
          if (!hintData.accepted) {
            hintData.accepted = true
            hintData.hint = '<i>getting hint...</i>'
          }
        },
      ).catch(
        err => {
          console.log('There was an error accepting the hint.', err)
          fadingMessage(document.querySelector('#hints'), 'There was an error accepting the hint.', err)
        },
      )
    },
    newHint(content) {
      let hintInfo = {'time': content.time, 'hint': content.hint, 'isNew': true, 'accepted': content.accepted}
      if (content.depends_on_unlock_uid === null) {
        this.hints.set(content.hint_uid, hintInfo)
      } else {
        if (!(this.unlocks.has(content.depends_on_unlock_uid))) {
          this.createBlankUnlock(content.depends_on_unlock_uid)
        }
        this.unlocks.get(content.depends_on_unlock_uid).hints.set(content.hint_uid, hintInfo)
      }
    },
    deleteHint(content) {
      if (!(this.hints.has(content.hint_uid) || (this.unlocks.has(content.depends_on_unlock_uid) &&
        this.unlocks.get(content.depends_on_unlock_uid).hints.has(content.hint_uid)))) {
        throw `WebSocket deleted invalid hint: ${content.hint_uid}`
      }
      if (content.depends_on_unlock_uid === null) {
        this.hints.delete(content.hint_uid)
      } else {
        this.unlocks.get(content.depends_on_unlock_uid).hints.delete(content.hint_uid)
      }
    },
    newUnlock(content) {
      if (!(this.unlocks.has(content.unlock_uid))) {
        this.createBlankUnlock(content.unlock_uid)
      }
      let unlockInfo = this.unlocks.get(content.unlock_uid)
      unlockInfo.unlock = content.unlock
      unlockInfo.guesses.add(content.guess)
      unlockInfo.isNew = true
    },
    changeUnlock(content) {
      if (!(this.unlocks.has(content.unlock_uid))) {
        throw `WebSocket changed invalid unlock: ${content.unlock_uid}`
      }
      this.unlocks.get(content.unlock_uid).unlock = content.unlock
    },
    deleteUnlockGuess(content) {
      if (!(this.unlocks.has(content.unlock_uid))) {
        throw `WebSocket deleted guess for invalid unlock: ${content.unlock_uid}`
      }
      let unlock = this.unlocks.get(content.unlock_uid)
      if (!(unlock.guesses.has(content.guess))) {
        throw `WebSocket deleted invalid guess (can happen if team made identical guesses): ${content.guess}`
      }
      unlock.guesses.delete(content.guess)
      if (unlock.guesses.size === 0) {
        this.unlocks.delete(content.unlock_uid)
      }
    },
    deleteUnlock(content) {
      if (!(this.unlocks.has(content.unlock_uid))) {
        throw `WebSocket deleted invalid unlock: ${content.unlock_uid}`
      }
      this.unlocks.delete(content.unlock_uid)
    },
  },
  mounted() {
    this.sock.handlers.set('new_unlock', new SocketHandler(this.newUnlock.bind(this), true, 'New unlock'))
    this.sock.handlers.set('old_unlock', new SocketHandler(this.newUnlock.bind(this)))
    this.sock.handlers.set('change_unlock', new SocketHandler(this.changeUnlock.bind(this), true, 'Updated unlock'))
    this.sock.handlers.set('delete_unlock', new SocketHandler(this.deleteUnlock.bind(this)))
    this.sock.handlers.set('delete_unlockguess', new SocketHandler(this.deleteUnlockGuess.bind(this)))
    this.sock.handlers.set('new_hint', new SocketHandler(this.newHint.bind(this), true, 'New hint'))
    this.sock.handlers.set('old_hint', new SocketHandler(this.newHint.bind(this)))
    this.sock.handlers.set('delete_hint', new SocketHandler(this.deleteHint.bind(this)))
    this.sock.send(JSON.stringify({'type': 'hints-plz', 'from': this.lastUpdated}))
    this.sock.send(JSON.stringify({'type': 'unlocks-plz'}))
  },
  props: [
    'hints',
    'sock',
    'unlocks',
  ],
}
