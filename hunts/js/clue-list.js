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

export default {
  computed: {
    none() {
      return this.clueData.hints.size === 0 && this.clueData.unlocks.size === 0 ? 'None yet' : ''
    },
    sortedHints() {
      return this.hintArray(this.clueData.hints)
    },
    sortedUnlocks() {
      return Array.from(this.clueData.unlocks.entries(), u => [u[0], u[1].unlock, u[1].guesses, this.hintArray(u[1].hints)])
    },
  },
  methods: {
    hintArray(hintMap) {
      return Array.from(hintMap.entries(), h => [h[0], h[1].time, h[1].hint]).sort((a, b) => (a[1].localeCompare(b[1])))
    },
  },
  props: [
    'clueData',
  ],
}
