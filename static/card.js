function toggleGrid(){
  var grid = document.getElementById('card-grid');
  var toggle = document.getElementById('dropdown-toggle');
  if(!grid) return;
  var open = grid.style.display === 'block';
  grid.style.display = open ? 'none' : 'block';
  grid.setAttribute('aria-hidden', open ? 'true':'false');
  if(toggle){ toggle.classList.toggle('open', !open); }
}

function selectCard(val){
  var input = document.getElementById('card-input');
  if(input){ input.value = val; }
  var grid = document.getElementById('card-grid');
  if(grid){ grid.style.display = 'none'; grid.setAttribute('aria-hidden','true'); }
  document.getElementById('card-select-form').submit();
}

function syncSaveFirstCard(){
  var sel = document.getElementById('card-input') ? document.getElementById('card-input').value : '';
  var saveInput = document.getElementById('save-first-card');
  if(saveInput) saveInput.value = sel;
}

function encodeId(key){ return 'sel-' + key.replace(/[^a-z0-9_\-]/gi, '_'); }

function toggleSelect(el){
  var val = el.getAttribute('data-val'); if(!val) return;
  var id = encodeId(val);
  var container = document.getElementById('selected-container');
  var existing = document.getElementById(id);

  var topKeys = ["cowboy_win","draw","bull_win"];
  if(topKeys.includes(val)){
    topKeys.forEach(function(k){
      if(k !== val){
        var otherId = encodeId(k);
        var otherEl = document.querySelector('.box[data-val="'+k+'"]');
        var otherInp = document.getElementById(otherId);
        if(otherInp){ otherInp.remove(); }
        if(otherEl){ otherEl.classList.remove('selected'); }
      }
    });
    if(existing){
      el.classList.remove('selected');
      existing.remove();
    } else {
      el.classList.add('selected');
      var inp=document.createElement('input');
      inp.type='hidden'; inp.name='selected_box'; inp.value=val; inp.id=id;
      container.appendChild(inp);
    }
    return;
  }

  if(existing){
    el.classList.remove('selected');
    existing.remove();
  } else {
    el.classList.add('selected');
    var inp=document.createElement('input');
    inp.type='hidden'; inp.name='selected_box'; inp.value=val; inp.id=id;
    container.appendChild(inp);
  }
}

function clearSelection(){
  document.querySelectorAll('.box.selected').forEach(function(b){ b.classList.remove('selected'); });
  var container = document.getElementById('selected-container');
  if(container){ container.innerHTML=''; }
}