/*
 * Copyright (C) 2021-2022 The Hunter2 Contributors.
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

import {encode} from 'html-entities'

export default {
  computed: {
    // These use an "unnecessary" ternary based on `this.rev` to workaround Vue 2.x's inability to react to changes in a Map or object fields
    // Based on https://newbedev.com/does-vue-support-reactivity-on-map-and-set-data-types
    none() {
      return this.hintRev && this.unlockRev && this.hints.size === 0 && this.unlocks.size === 0 ? 'None yet' : ''
    },
    sortedHints() {
      return this.hintRev ? this.hintArray(this.hints) : []
    },
    sortedUnlocks() {
      return this.unlockRev ? Array.from(this.unlocks.entries(), u => [u[0], u[1].unlock, u[1].guesses, this.hintArray(u[1].hints)]) : []
    },
  },
  data() {
    return {
      hints: new Map(),
      unlocks: new Map(),
      hintRev: 1,
      unlockRev: 1,
    }
  },
  methods: {
    createBlankUnlock(uid) {
      this.unlocks.set(uid, {'unlock': null, 'guesses': new Set(), 'hints': new Map()})
    },
    hintArray(hintMap) {
      return Array.from(hintMap.entries(), h => [h[0], h[1].time, h[1].hint]).sort((a, b) => (a[1].localeCompare(b[1])))
    },
    newHint(content) {
      if (content.depends_on_unlock_uid === null) {
        this.hints.set(content.hint_uid, {'time': content.time, 'hint': content.hint})
        this.hintRev++
      } else {
        if (!(this.unlocks.has(content.depends_on_unlock_uid))) {
          this.createBlankUnlock(content.depends_on_unlock_uid)
        }
        this.unlocks.get(content.depends_on_unlock_uid).hints.set(content.hint_uid, {'time': content.time, 'hint': content.hint})
        this.unlockRev++
      }
    },
    deleteHint(content) {
      if (!(this.hints.has(content.hint_uid) || (this.unlocks.has(content.depends_on_unlock_uid) &&
        this.unlocks.get(content.depends_on_unlock_uid).hints.has(content.hint_uid)))) {
        throw `WebSocket deleted invalid hint: ${content.hint_uid}`
      }
      if (content.depends_on_unlock_uid === null) {
        this.hints.delete(content.hint_uid)
        this.hintRev++
      } else {
        this.unlocks.get(content.depends_on_unlock_uid).hints.delete(content.hint_uid)
        this.unlockRev++
      }
    },
    newUnlock(content) {
      if (!(this.unlocks.has(content.unlock_uid))) {
        this.createBlankUnlock(content.unlock_uid)
      }
      let unlockInfo = this.unlocks.get(content.unlock_uid)
      unlockInfo.unlock = content.unlock
      unlockInfo.guesses.add(encode(content.guess))
      this.unlockRev++
    },
    changeUnlock(content) {
      if (!(this.unlocks.has(content.unlock_uid))) {
        throw `WebSocket changed invalid unlock: ${content.unlock_uid}`
      }
      this.unlocks.get(content.unlock_uid).unlock = content.unlock
      this.unlockRev++
    },
    deleteUnlockGuess(content) {
      if (!(this.unlocks.has(content.unlock_uid))) {
        throw `WebSocket deleted guess for invalid unlock: ${content.unlock_uid}`
      }
      let unlock = this.unlocks.get(content.unlock_uid)
      let encodedGuess = encode(content.guess)
      if (!(unlock.guesses.has(encodedGuess))) {
        throw `WebSocket deleted invalid guess (can happen if team made identical guesses): ${content.guess}`
      }
      unlock.guesses.delete(encodedGuess)
      if (unlock.guesses.size === 0) {
        this.unlocks.delete(content.unlock_uid)
      }
      this.unlockRev++
    },
    deleteUnlock(content) {
      if (!(this.unlocks.has(content.unlock_uid))) {
        throw `WebSocket deleted invalid unlock: ${content.unlock_uid}`
      }
      this.unlocks.delete(content.unlock_uid)
      this.unlockRev++
    },
  },
}
