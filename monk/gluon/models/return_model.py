from gluon.models.imports import *
from system.imports import *
from gluon.models.models import *
from gluon.models.common import create_final_layer
from gluon.models.common import get_layer_uid
from gluon.models.layers import custom_model_get_layer
from gluon.models.layers import addBlock
from gluon.models.initializers import initialize_network



@accepts(dict, path=[str, bool], final=bool, resume=bool, external_path=[bool, str, list], post_trace=True)
@TraceFunction(trace_args=False, trace_rv=False)
def load_model(system_dict, path=False, final=False, resume=False, external_path=False):
    if(final):
        if(path):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore");
                finetune_net = mx.gluon.SymbolBlock.imports(path + 'final-symbol.json', ['data'], path + 'final-0000.params');
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                finetune_net = mx.gluon.SymbolBlock.imports(system_dict["model_dir_relative"] + 'final-symbol.json', ['data'], system_dict["model_dir_relative"] + 'final-0000.params');
    if(resume):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore");
            finetune_net = mx.gluon.SymbolBlock.imports(system_dict["model_dir_relative"] + 'resume_state-symbol.json', ['data'], system_dict["model_dir_relative"] + 'resume_state-0000.params');
 
    if(external_path):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore");
            finetune_net = mx.gluon.SymbolBlock.imports(external_path[0], ['data'], external_path[1]);

    return finetune_net;



@accepts(dict, post_trace=True)
@TraceFunction(trace_args=False, trace_rv=False)
def setup_model(system_dict):
    if(system_dict["model"]["type"] == "pretrained"):
        model_name = system_dict["model"]["params"]["model_name"];
        use_pretrained = system_dict["model"]["params"]["use_pretrained"];
        freeze_base_network = system_dict["model"]["params"]["freeze_base_network"];
        custom_network = system_dict["model"]["custom_network"];
        final_layer = system_dict["model"]["final_layer"];
        num_classes = system_dict["dataset"]["params"]["num_classes"];

        finetune_net, model_name = get_base_model(model_name, use_pretrained, num_classes, freeze_base_network);

        if(len(custom_network)):
            if(final_layer):
                if(model_name in set1):
                    finetune_net = create_final_layer(finetune_net, custom_network, num_classes, set=1);
                elif(model_name in set2):
                    finetune_net = create_final_layer(finetune_net, custom_network, num_classes, set=2);
                elif(model_name in set3):
                    finetune_net = create_final_layer(finetune_net, custom_network, num_classes, set=3);
            else:
                print("Final layer not assigned");
                return 0;
        else:
            if(model_name in set1):
                with finetune_net.name_scope():
                    finetune_net.output = nn.Dense(num_classes, weight_initializer=init.Xavier());
                    finetune_net.output.initialize(init.Xavier(), ctx = ctx);
            elif(model_name in set2):
                net = nn.HybridSequential();
                with net.name_scope():
                    net.add(nn.Conv2D(num_classes, kernel_size=(1, 1), strides=(1, 1), weight_initializer=init.Xavier()));
                    net.add(nn.Flatten());
                with finetune_net.name_scope():
                    finetune_net.output = net;
                    finetune_net.output.initialize(init.Xavier(), ctx = ctx)
            elif(model_name in set3):
                with finetune_net.name_scope():
                    finetune_net.fc = nn.Dense(num_classes, weight_initializer=init.Xavier());
                    finetune_net.fc.initialize(init.Xavier(), ctx = ctx)


        if(not use_pretrained):
            finetune_net.initialize(init.Xavier(), ctx = ctx)


        system_dict["local"]["model"] = finetune_net;

        return system_dict;

    else:
        count = [];
        for i in range(len(names)):
            count.append(1);

        network_stack = system_dict["custom_model"]["network_stack"];
        G=nx.DiGraph()
        G.add_node("Net", pos=(1,1))
        sequential_first = "data";
        sequential_second, count = get_layer_uid(network_stack[0], count)

        count = [];
        for i in range(len(names)):
            count.append(1);

        position = 1;
        G.add_node(sequential_first, pos=(2,1))
        position += 1;

        net = nn.HybridSequential();
        max_width = 1;
        for i in range(len(network_stack)):
            if(type(network_stack[i]) == list):
                branch_end_points = [];
                branch_lengths = [];
                branches = [];
                branch_net = [];


                if(max_width < len(network_stack[i])-2):
                    max_width = len(network_stack[i])-2
                for j in range(len(network_stack[i])-1):
                    small_net = [];
                    branch_net.append(nn.HybridSequential())
                    branch_first = sequential_first
                    branch_position = position
                    column = j+2;
                    for k in range(len(network_stack[i][j])):
                        branch_second, count = get_layer_uid(network_stack[i][j][k], count);
                        small_net.append(custom_model_get_layer(network_stack[i][j][k]));
                        branch_net[j].add(custom_model_get_layer(network_stack[i][j][k]));
                        G.add_node(branch_second, pos=(column, branch_position));
                        branch_position += 1;
                        G.add_edge(branch_first, branch_second);
                        branch_first = branch_second;

                        if(k == len(network_stack[i][j])-1):
                            branch_end_points.append(branch_second);
                            branch_lengths.append(len(network_stack[i][j]));
                    branches.append(small_net);

                position += max(branch_lengths);
                position += 1;

                sequential_second, count = get_layer_uid(network_stack[i][-1], count)
                if(network_stack[i][-1]["name"] == "concatenate"):
                    subnetwork = contrib_nn.HybridConcurrent(axis=1);
                    for j in range(len(network_stack[i])-1):
                        #print(branch_net[j])
                        subnetwork.add(branch_net[j]);

                else:
                    subnetwork = addBlock(branches);

                G.add_node(sequential_second, pos=(2, position));
                position += 1;
                for i in range(len(branch_end_points)):
                    G.add_edge(branch_end_points[i], sequential_second);
                sequential_first = sequential_second;
                net.add(subnetwork)


            else:
                sequential_second, count = get_layer_uid(network_stack[i], count)
                net.add(custom_model_get_layer(network_stack[i]));
                G.add_node(sequential_second, pos=(2, position))
                position += 1;
                G.add_edge(sequential_first, sequential_second);
                sequential_first = sequential_second;


        net = initialize_network(net, system_dict["custom_model"]["network_initializer"]);

        if(max_width == 1):
            G.add_node("monk", pos=(3, position));
        else:
            G.add_node("monk", pos=(max_width + 3, position))
        pos=nx.get_node_attributes(G,'pos')

        plt.figure(3, figsize=(8, 12 + position//6)) 
        nx.draw_networkx(G, pos, with_label=True, font_size=16, node_color="yellow", node_size=100)
        plt.savefig("graph.png");


        system_dict["local"]["model"] = net;

        return system_dict;


@accepts(list, post_trace=True)
@TraceFunction(trace_args=False, trace_rv=False)
def debug_custom_model(network_stack):
    count = [];
    for i in range(len(names)):
        count.append(1);

    G=nx.DiGraph()
    G.add_node("Net", pos=(1,1))
    sequential_first = "data";
    sequential_second, count = get_layer_uid(network_stack[0], count)

    count = [];
    for i in range(len(names)):
        count.append(1);

    position = 1;
    G.add_node(sequential_first, pos=(2,1))
    position += 1;


    max_width = 1;
    for i in range(len(network_stack)):
        if(type(network_stack[i]) == list):
            branch_end_points = [];
            branch_lengths = [];
            branches = [];
            branch_net = [];


            if(max_width < len(network_stack[i])-2):
                max_width = len(network_stack[i])-2
            for j in range(len(network_stack[i])-1):
                branch_first = sequential_first
                branch_position = position
                column = j+2;
                for k in range(len(network_stack[i][j])):
                    branch_second, count = get_layer_uid(network_stack[i][j][k], count);
                    G.add_node(branch_second, pos=(column, branch_position));
                    branch_position += 1;
                    G.add_edge(branch_first, branch_second);
                    branch_first = branch_second;

                    if(k == len(network_stack[i][j])-1):
                        branch_end_points.append(branch_second);
                        branch_lengths.append(len(network_stack[i][j]));

            position += max(branch_lengths);
            position += 1;

            sequential_second, count = get_layer_uid(network_stack[i][-1], count)

            G.add_node(sequential_second, pos=(2, position));
            position += 1;
            for i in range(len(branch_end_points)):
                G.add_edge(branch_end_points[i], sequential_second);
            sequential_first = sequential_second;


        else:
            sequential_second, count = get_layer_uid(network_stack[i], count)
            G.add_node(sequential_second, pos=(2, position))
            position += 1;
            G.add_edge(sequential_first, sequential_second);
            sequential_first = sequential_second;


    if(max_width == 1):
        G.add_node("monk", pos=(3, position));
    else:
        G.add_node("monk", pos=(max_width + 3, position))
    pos=nx.get_node_attributes(G,'pos')

    plt.figure(3, figsize=(8, 12 + position//6)) 
    nx.draw_networkx(G, pos, with_label=True, font_size=16, node_color="yellow", node_size=100)
    plt.savefig("graph.png");