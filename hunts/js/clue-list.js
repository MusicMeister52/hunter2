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

export default {
  computed: {
    none() {
      return this.clueData.hints.size === 0 && this.clueData.unlocks.size === 0 ? 'None yet' : ''
    },
    sortedHints() {
      return this.hintArray(this.clueData.hints)
    },
    sortedUnlocks() {
      return Array.from(this.clueData.unlocks.entries(), u => [u[0], {
        unlock: u[1].unlock,
        guesses: u[1].guesses,
        isNew: u[1].isNew,
        hints: this.hintArray(u[1].hints),
      }])
    },
  },
  methods: {
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
            hintData = this.clueData.hints.get(hintId)
          } else {
            hintData = this.clueData.unlocks.get(unlockId).hints.get(hintId)
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
  },
  props: [
    'clueData',
  ],
}
