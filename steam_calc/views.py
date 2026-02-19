# steam_calc/views.py
from django.shortcuts import render
from iapws import IAPWS97
import json
import math

def generate_saturation_dome():
    """Generate T-s diagram saturation dome data"""
    liquid_line = []
    vapor_line = []
    
    for t_celsius in range(0, 374, 10):
        t_kelvin = t_celsius + 273.15
        try:
            sat_liquid = IAPWS97(T=t_kelvin, x=0)
            sat_vapor = IAPWS97(T=t_kelvin, x=1)
            liquid_line.append({'x': sat_liquid.s, 'y': t_celsius})
            vapor_line.append({'x': sat_vapor.s, 'y': t_celsius})
        except:
            pass
            
    # Add approximate critical point
    liquid_line.append({'x': 4.406, 'y': 373.946})
    vapor_line.append({'x': 4.406, 'y': 373.946})
    
    return liquid_line, vapor_line

def steam_calculator(request):
    context = {}
    
    # Generate Saturation Dome
    liquid_line, vapor_line = generate_saturation_dome()
    context['liquid_line'] = json.dumps(liquid_line)
    context['vapor_line'] = json.dumps(vapor_line)

    if request.method == "POST":
        mode = request.POST.get('mode', 'state_point')
        
        if mode == 'rankine_cycle':
            context['active_mode'] = 'rankine'
            handle_rankine_cycle(request, context)
        else:
            context['active_mode'] = 'state'
            handle_state_point(request, context)

    return render(request, 'index.html', context)

def handle_state_point(request, context):
    """Handle single state point calculation"""
    p_input = request.POST.get('pressure')
    t_input = request.POST.get('temperature')
    p_unit = request.POST.get('p_unit')
    t_unit = request.POST.get('t_unit')
    
    try:
        p_val = float(p_input)
        t_val = float(t_input)
        
        # Convert Pressure to MPa
        if p_unit == 'bar':
            p_mpa = p_val / 10.0
        elif p_unit == 'pa':
            p_mpa = p_val / 1000000.0
        elif p_unit == 'atm':
            p_mpa = p_val * 0.101325
            
        # Convert Temperature to Kelvin
        if t_unit == 'c':
            t_k = t_val + 273.15
        else:
            t_k = t_val
            
        # Calculate state
        steam = IAPWS97(P=p_mpa, T=t_k)
        
        context.update({
            'success': True,
            'p': p_val, 't': t_val,
            'p_unit': p_unit, 't_unit': t_unit,
            'h': round(steam.h, 2),
            's': round(steam.s, 4),
            'v': round(steam.v, 5),
            'point_s': steam.s,
            'point_t': t_k - 273.15
        })
        
        if steam.phase == 'Liquid':
            context['state'] = 'Compressed Liquid'
            context['x'] = '0'
        elif steam.phase == 'Gas':
            context['state'] = 'Superheated Steam'
            context['x'] = '1'
        elif steam.phase == 'Two-phase':
            context['state'] = 'Wet Steam'
            context['x'] = round(steam.x, 4)
            
            intermediate_data = []
            for ix in [0.2, 0.4, 0.6, 0.8]:
                int_steam = IAPWS97(P=p_mpa, x=ix)
                intermediate_data.append({
                    'x': ix,
                    'h': round(int_steam.h, 2),
                    's': round(int_steam.s, 4),
                    'v': round(int_steam.v, 5)
                })
            context['intermediate_data'] = intermediate_data
            
    except NotImplementedError as e:
        if "out of bound" in str(e).lower():
            context['error'] = "The provided temperature and pressure exceed the valid limits of the IAPWS-97 steam tables. Please enter physically realistic values."
        else:
            context['error'] = f"Thermodynamic error: {str(e)}"
    except ValueError as e:
        context['error'] = f"Input Error: {str(e)}"
    except Exception as e:
        context['error'] = f"An unexpected calculation error occurred. Verify your inputs."


def handle_rankine_cycle(request, context):
    """Handle Rankine cycle analysis"""
    try:
        # Get inputs
        p_low = float(request.POST.get('p_cond', 0.05))  # Bar
        p_high = float(request.POST.get('p_boiler', 10))  # Bar
        t_high = float(request.POST.get('t_boiler', 450))  # °C
        pump_eff = float(request.POST.get('pump_eff', 85)) / 100  # Convert to decimal
        turbine_eff = float(request.POST.get('turbine_eff', 85)) / 100
        
        # 1. Logical Physics Checks
        if p_low >= p_high:
            raise ValueError("Physics Violation: Boiler pressure must be strictly greater than Condenser pressure.")
        if pump_eff <= 0 or turbine_eff <= 0 or pump_eff > 1 or turbine_eff > 1:
            raise ValueError("Efficiencies must be between 1% and 100%.")

        # Convert to MPa
        p_low_mpa = p_low / 10.0
        p_high_mpa = p_high / 10.0
        t_high_k = t_high + 273.15
        
        # State 1: Saturated liquid at low pressure (pump inlet)
        state1 = IAPWS97(P=p_low_mpa, x=0)
        
        # State 2s: Isentropic compression (ideal)
        state2s = IAPWS97(P=p_high_mpa, s=state1.s)
        
        # State 2: Actual compression with efficiency
        h2_actual = state1.h + (state2s.h - state1.h) / pump_eff
        state2 = IAPWS97(P=p_high_mpa, h=h2_actual)
        
        # State 3: Superheated steam at high pressure
        # (If temperature is exactly saturation temp, phase might be Two-phase or Gas)
        state3 = IAPWS97(P=p_high_mpa, T=t_high_k)
        
        # State 4s: Isentropic expansion (ideal)
        state4s = IAPWS97(P=p_low_mpa, s=state3.s)
        
        # State 4: Actual expansion with efficiency
        h4_actual = state3.h - (state3.h - state4s.h) * turbine_eff
        state4 = IAPWS97(P=p_low_mpa, h=h4_actual)
        
        # Calculate cycle parameters
        w_pump = state2.h - state1.h
        q_in = state3.h - state2.h
        w_turbine = state3.h - state4.h
        w_net = w_turbine - w_pump
        efficiency = (w_net / q_in * 100) if q_in > 0 else 0
        
        # Ideal cycle efficiency (Carnot-like, for reference)
        t_high_abs = t_high + 273.15
        t_low_abs = state1.T
        carnot_eff = (1 - t_low_abs / t_high_abs) * 100
        
        # Build cycle points for visualization
        cycle_points = [
            {'x': state1.s, 'y': state1.T - 273.15, 'label': 'State 1'},
            {'x': state2.s, 'y': state2.T - 273.15, 'label': 'State 2'},
            {'x': state3.s, 'y': state3.T - 273.15, 'label': 'State 3'},
            {'x': state4.s, 'y': state4.T - 273.15, 'label': 'State 4'},
            {'x': state1.s, 'y': state1.T - 273.15, 'label': 'State 1'}  # Close cycle
        ]
        
        context.update({
            'success': True,
            'rankine_cycle': True,
            'cycle_points': json.dumps(cycle_points),
            'p_low': p_low,
            'p_high': p_high,
            't_high': t_high,
            'pump_eff': pump_eff * 100,
            'turbine_eff': turbine_eff * 100,
            'state1': {
                'p': round(state1.P * 10, 3), 'T': round(state1.T - 273.15, 2),
                'h': round(state1.h, 2), 's': round(state1.s, 4),
                'x': '0 (sat. liquid)', 'phase': 'Saturated Liquid'
            },
            'state2': {
                'p': round(state2.P * 10, 3), 'T': round(state2.T - 273.15, 2),
                'h': round(state2.h, 2), 's': round(state2.s, 4),
                'x': round(state2.x, 4) if hasattr(state2, 'x') else 'N/A',
                'phase': state2.phase
            },
            'state3': {
                'p': round(state3.P * 10, 3), 'T': round(state3.T - 273.15, 2),
                'h': round(state3.h, 2), 's': round(state3.s, 4),
                'x': '1 (sat. vapor)' if state3.phase == 'Gas' else round(state3.x, 4),
                'phase': 'Superheated Steam'
            },
            'state4': {
                'p': round(state4.P * 10, 3), 'T': round(state4.T - 273.15, 2),
                'h': round(state4.h, 2), 's': round(state4.s, 4),
                'x': round(state4.x, 4) if hasattr(state4, 'x') else 'N/A',
                'phase': state4.phase
            },
            'w_pump': round(w_pump, 2),
            'q_in': round(q_in, 2),
            'w_turbine': round(w_turbine, 2),
            'w_net': round(w_net, 2),
            'efficiency': round(efficiency, 2),
            'carnot_eff': round(carnot_eff, 2),
        })
        
    except NotImplementedError as e:
        if "out of bound" in str(e).lower():
            context['error'] = "The provided parameters exceed the valid limits of the IAPWS-97 formulations. Please verify that your Boiler Temperature isn't impossibly high or low."
        else:
            context['error'] = f"Thermodynamic error: {str(e)}"
    except ValueError as e:
        context['error'] = str(e)  # Catch our custom logical physics errors
    except Exception as e:
        context['error'] = "An unexpected error occurred. Please ensure all inputs are valid numbers."