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

import URI from 'urijs'
import 'bootstrap/js/dist/button'
import 'bootstrap/js/dist/collapse'

import HumanDateTime from '../human-datetime.vue'
import HumanDuration from '../human-duration.vue'

export default {
  components: {
    'human-datetime': HumanDateTime,
    'human-duration': HumanDuration,
  },
  computed: {
    sortedPuzzles() {
      function comparePuzzles(a, b) {
        const ad = new Date(a.guesses[0].given)
        const bd = new Date(b.guesses[0].given)
        return bd - ad
      }
      return [...this.puzzles].sort(comparePuzzles)
    },
  },
  created: function() {
    this.updateData(true)
  },
  data () {
    return {
      puzzles: [],
      solved_puzzles: [],
      'guess_fields': [
        'user',
        'guess',
        'given',
      ],
      'clue_fields': [
        'type',
        'text',
        'received_at',
      ],
    }
  },
  methods: {
    anchor: function() { return window.location.hash.substring(1) },
    updateData: function(force) {
      clearTimeout(this.timer)
      if (force || this.autoUpdate) {
        let url = URI(this.href)
        let v = this
        fetch(url).then(
          response => response.json(),
        ).then(
          data => {
            v.puzzles = data.puzzles
            v.solved_puzzles = data.solved_puzzles
          },
        )
        if (this.autoUpdate) {
          this.timer = setTimeout(this.updateData, 5000)
        }
      }
    },
  },
  props: ['href'],
}
